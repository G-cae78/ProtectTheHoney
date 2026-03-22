# Machine Learning

This folder contains everything related to the ML side of ProtectTheHoney: the training notebooks, the production inference pipeline, the LLM-driven WAF rule generation system, saved model artifacts, and the raw datasets.

---

## How it all fits together

```
Historical nginx logs (Datasets/)
        |
        v
HDBSCAN_train-2.ipynb   <-- trains the model, saves artifacts
        |
        v
Trained Artifacts/      <-- 7 joblib files per model version
        |
        v
GCP-VM-Pipeline/        <-- runs on the live server every 5 minutes
  pipeline.py           <-- parses logs, builds feature matrix
  run_batch.py          <-- loads artifacts, runs inference, writes outputs
        |
        v
rollup JSON + pred CSV
        |
        v
LLM/Deploy-Pipeline/    <-- FastAPI service on same GCP VM
  LLM_pipeline.py       <-- reads rollup, generates Cloudflare WAF rules
  Feed_LLM_pipeline.py  <-- sends batch predictions to the pipeline
        |
        v
Cloudflare WAF rules + Jira tickets
```

---

## Notebooks

### HDBSCAN_train-2.ipynb (use this one)

The main training notebook. Loads nginx logs from multiple sources (Cloudflare, BunnyCDN, direct), runs the feature engineering pipeline, tunes and fits HDBSCAN, then interprets and labels each cluster. Saves all 7 artifacts to a timestamped folder under `Trained Artifacts/`.

The model currently produces 22 clusters (0-21) plus noise (-1). Each one maps to a recognisable attack pattern, see the cluster table in the root README.

### HDBSCAN_train-1.ipynb

The first training run, done on an earlier and smaller dataset. Kept for reference. The cluster numbering is different and the artifacts it produced are in `Trained Artifacts/artifacts-20th-Jan(1)/`.

### drift_analysis.ipynb

Checks whether the current model is still valid. Loads the training artifacts, runs the same feature pipeline on a newer log dataset, then compares cluster centroids using cosine distance. If drift scores are high it's a sign the model needs retraining.

### Kmeans.ipynb

An early experiment using K-Means as an alternative to HDBSCAN. Abandoned because HDBSCAN handled noise better and produced more interpretable clusters. Kept here for completeness.

### LLM/llm-testing.ipynb

A scratchpad notebook for experimenting with LLM-based WAF rule generation before the proper pipeline was built. Tests different models (Groq, Anthropic, HuggingFace, Cohere) against hardcoded rollup payloads representing various attack scenarios.

---

## GCP-VM-Pipeline/

The code that runs in production on the GCP instance at `/opt/honey/pipeline/`.

### pipeline.py

Feature engineering shared between training and inference. The key functions are:

- `parse_nginx_lines(lines)` -- parses raw nginx combined log format into a DataFrame
- `make_5min_windows(df)` -- groups log rows into 5-minute windows per IP, computes request counts, unique paths, status code ratios
- `build_X(windows, vectorizer, scaler, num_cols)` -- combines TF-IDF on request paths with scaled numeric features into a sparse matrix

The local `pipeline.py` in the root of `Machine Learning/` is a slightly older version without the nginx parser. Only the GCP version should be used for production.

### run_batch.py

The cron entry point. On each run it:

1. Reads the offset file to find where it left off in `nginx_access.log`
2. Parses only the new lines since last run
3. Builds the feature matrix using `pipeline.py`
4. Assigns clusters via cosine nearest-neighbour index (not HDBSCAN.predict, which doesn't generalise well to new data)
5. Marks windows in the top 15% by distance as noise (-1), catching anything the model hasn't seen before
6. Writes a `pred_<timestamp>.csv` and a `rollup_<timestamp>.json` to `/opt/honey/results/`

---

## LLM/

### Deploy-Pipeline/LLM_pipeline.py

A FastAPI service that takes the rollup JSON produced by `run_batch.py` and generates Cloudflare WAF rules using an LLM. The main flow is:

1. Receives a rollup payload (cluster summaries, top paths, status code breakdowns)
2. Runs a tool-use loop with a Groq-hosted LLM (tries up to 6 models if one fails)
3. The LLM can call three tools: `query_knowledgebase`, `create_jira_ticket`, `create_consolidated_firewall_rules`
4. `query_knowledgebase` does semantic search over a 7,172-entry cybersecurity knowledge base using Voyage AI embeddings
5. `create_consolidated_firewall_rules` groups patterns by action (block/challenge/js_challenge), merges them with OR logic to stay within Cloudflare's rule budget, and pushes rules via the Cloudflare API
6. A Jira ticket is also created for each incident

The service tracks which clusters it has already handled in a session so it doesn't generate duplicate rules. It also syncs with the current live Cloudflare rules on startup.

### Deploy-Pipeline/Feed_LLM_pipeline.py

A small utility that reads prediction CSVs and rollup JSONs and POSTs them to `LLM_pipeline.py`'s batch endpoint. Used for replaying past predictions or testing the pipeline manually.

### knowledgebase.json

A 7,172-entry knowledge base in JSON-LD format covering common attack patterns, CVEs, and Cloudflare expression syntax. The LLM queries this via semantic search when generating rules.

### llm-testing.ipynb

See above under Notebooks.

---

## Trained Artifacts/

Four saved model versions, each with the same 7 files:

| File | What it is |
|------|-----------|
| `hdbscan.joblib` | The fitted HDBSCAN model |
| `tfidf.joblib` | TF-IDF vectorizer fitted on request paths |
| `scaler.joblib` | StandardScaler for numeric features |
| `X_train.joblib` | Training feature matrix (used in drift analysis) |
| `labels_train.joblib` | Cluster label for each training window |
| `nn_index.joblib` | Cosine nearest-neighbour index used at inference time |
| `num_cols.joblib` | Ordered list of numeric column names, keeps training and inference aligned |

| Version | Date | Notes |
|---------|------|-------|
| `artifacts-20th-Jan(1)/` | Jan 2026 | First training run |
| `artifacts-17th-Feb(2)/` | Feb 2026 | Retrained on more data |
| `20260308_145715/` | 8 Mar 2026 | |
| `20260312_113715/` | 12 Mar 2026 | Latest, currently in production |

To deploy a new version, copy the 7 joblib files to the GCP instance:

```bash
scp "Trained Artifacts/20260312_113715/"*.joblib \
    username@<instance-ip>:/opt/honey/artifacts/
```

Then do a manual test run:

```bash
sudo python3 /opt/honey/pipeline/run_batch.py
```

---

## Datasets/

Raw nginx logs used for training and drift analysis.

| File | Date range | Notes |
|------|-----------|-------|
| `nginx_access_21Feb-7Mar_2026.log` | Feb-Mar 2026 | Primary training dataset |
| `access_last10days(BunnyCDN).log` | Mar 2026 | Used in drift analysis |
| `nginx_access_19Dec-27Dec_2025(Cloudflare).log` | Dec 2025 | With Cloudflare WAF active |
| `nginx_access_16Jan(No CDN).log` | Jan 2026 | Before CDN deployment |
| `honeypot_logs.csv` | Ongoing | Credential capture data from Lambda |
| `nginx_errors_21Feb-7Mar_2026.log` | Feb-Mar 2026 | Error logs |

---

## Retraining

If `drift_analysis.ipynb` shows high drift scores, retrain like this:

1. Add new log files to `Datasets/`
2. Run `HDBSCAN_train-2.ipynb` top to bottom
3. Artifacts are saved automatically to a timestamped folder
4. Copy the new artifacts to the GCP instance (see above)
5. Restart or re-run `run_batch.py` manually to confirm it picks up the new model

---

## Visualization

`honeypot_clusters_3d.html` is an interactive 3D Plotly visualization of the training clusters. Open it in a browser to explore how the clusters are distributed in feature space.
