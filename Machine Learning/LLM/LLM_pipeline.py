"""
LLM_pipeline.py
---------------
Standalone agentic LLM pipeline for cybersecurity threat analysis.

Called by the clustering model with rollup JSON and pred CSV paths.

Usage:
    from LLM_pipeline import run_pipeline

    result = run_pipeline(
        rollup_payload=rollup_json_str,   # JSON string from clustering model
        pred_csv_path="pred_20260308T152002Z.csv",  # path to pred file
    )

Or from CLI:
    python LLM_pipeline.py --rollup rollup.json --pred pred_20260308T152002Z.csv

Embedding cache:
    On first run, embeds knowledgebase.json and saves to kb_embeddings.pkl.
    Subsequent runs load from cache — no re-embedding needed.
"""

import os
import json
import pickle
import argparse
import logging
from pathlib import Path
from time import time

import numpy as np
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
VOYAGE_API_KEY     = os.getenv("VOYAGE_API_KEY")
JIRA_API_TOKEN     = os.getenv("JIRA_API_TOKEN")
JIRA_AUTH_EMAIL    = os.getenv("JIRA_AUTH_EMAIL")
JIRA_REQUEST_URL   = os.getenv("JIRA_REQUEST_URL")
JIRA_PROJECT_KEY   = os.getenv("JIRA_PROJECT_KEY")
CLOUDFLARE_API_TOKEN  = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_ZONE_ID    = os.getenv("CLOUDFLARE_ZONE_ID")

KB_PATH            = Path("knowledgebase.json")
EMBED_CACHE_PATH   = Path("kb_embeddings.pkl")
EMBED_MODEL        = "voyage-3-lite"
EMBED_BATCH_SIZE   = 32
GROQ_MODEL         = "llama-3.3-70b-versatile"
MAX_TOOL_ITERS     = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cluster severity reference (training-time output — static context)
# ---------------------------------------------------------------------------

CLUSTER_SEVERITY_DICT = {
    -1: {"cluster_label": "PHP webshell deployment / backdoor probe", "label_conf": 0.342, "matched_patterns": "0\\.php, \\.php$", "secondary_labels": "PHPUnit RCE probing (eval-stdin.php); Generic login discovery / credential targeting", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Attacker probing for or attempting to access PHP webshells / backdoors for persistent access."},
    0:  {"cluster_label": "Path traversal / directory escape probe", "label_conf": 0.723, "matched_patterns": "\\.%0e/, cgi-bin/.*bin/sh", "secondary_labels": "", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Directory traversal attempt to escape web root and access sensitive system files (e.g. /etc/passwd)."},
    1:  {"cluster_label": "Git / source code exposure scan", "label_conf": 0.774, "matched_patterns": "\\.git/config", "secondary_labels": "GeoServer / infrastructure admin probe; Secrets discovery (.env harvesting)", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Attacker scanning for exposed .git directories which could leak full source code and credentials."},
    2:  {"cluster_label": "Generic login discovery / credential targeting", "label_conf": 0.929, "matched_patterns": "/login(\\.|/|$), login\\.jsp, logon\\.html", "secondary_labels": "Cisco / VPN / firewall probe; IoT / embedded device exploit scan", "severity": "MEDIUM", "severity_rank": 2, "jira_priority": "Medium", "jira_description": "Broad scanning for login panels across multiple frameworks to identify authentication endpoints."},
    3:  {"cluster_label": "Favicon / robots.txt fingerprinting", "label_conf": 0.784, "matched_patterns": "^/favicon\\.ico$, favicon\\.ico/ads\\.txt", "secondary_labels": "PHP webshell deployment / backdoor probe", "severity": "LOW", "severity_rank": 3, "jira_priority": "Low", "jira_description": "Passive fingerprinting via favicon hash and robots.txt to identify technology stack before active exploitation."},
    4:  {"cluster_label": "Favicon / robots.txt fingerprinting", "label_conf": 0.820, "matched_patterns": "^/favicon\\.ico$, ^/robots\\.txt$", "secondary_labels": "", "severity": "LOW", "severity_rank": 3, "jira_priority": "Low", "jira_description": "Passive fingerprinting via favicon hash and robots.txt to identify technology stack before active exploitation."},
    5:  {"cluster_label": "Favicon / robots.txt fingerprinting", "label_conf": 0.873, "matched_patterns": "^/favicon\\.ico$, ^/robots\\.txt$", "secondary_labels": "", "severity": "LOW", "severity_rank": 3, "jira_priority": "Low", "jira_description": "Passive fingerprinting via favicon hash and robots.txt to identify technology stack before active exploitation."},
    6:  {"cluster_label": "Uncategorized / miscellaneous scanning", "label_conf": 0.000, "matched_patterns": "", "secondary_labels": "", "severity": "LOW", "severity_rank": 3, "jira_priority": "Low", "jira_description": None},
    7:  {"cluster_label": "PHP webshell deployment / backdoor probe", "label_conf": 0.377, "matched_patterns": "0\\.php, \\.php$, adminfuns\\.php, class-t\\.api\\.", "secondary_labels": "Cloud metadata / config exposure; WordPress exploitation / admin enumeration", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Attacker probing for or attempting to access PHP webshells / backdoors for persistent access."},
    8:  {"cluster_label": "PHP webshell deployment / backdoor probe", "label_conf": 0.029, "matched_patterns": "adminfuns\\.php, ws\\.php", "secondary_labels": "Cloud metadata / config exposure", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Attacker probing for or attempting to access PHP webshells / backdoors for persistent access."},
    9:  {"cluster_label": "Exchange / Autodiscover / RDP probe", "label_conf": 0.229, "matched_patterns": "autodiscover/autodiscover\\.json, developmentserver", "secondary_labels": "Secrets discovery (.env harvesting); Generic login discovery / credential targeting", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Probing for exposed Microsoft Exchange, OWA, or RDP services — common ransomware initial access vector."},
    10: {"cluster_label": "PHP webshell deployment / backdoor probe", "label_conf": 0.036, "matched_patterns": "\\.php$, ms\\.php", "secondary_labels": "", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Attacker probing for or attempting to access PHP webshells / backdoors for persistent access."},
    11: {"cluster_label": "Exchange / Autodiscover / RDP probe", "label_conf": 0.254, "matched_patterns": "RDWeb/Pages, ReportServer, autodiscover/autodiscover", "secondary_labels": "Generic login discovery / credential targeting", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Probing for exposed Microsoft Exchange, OWA, or RDP services — common ransomware initial access vector."},
    12: {"cluster_label": "PHP webshell deployment / backdoor probe", "label_conf": 0.955, "matched_patterns": "0\\.php, \\.php$", "secondary_labels": "WordPress exploitation / admin enumeration", "severity": "CRITICAL", "severity_rank": 0, "jira_priority": "Highest", "jira_description": "Attacker probing for or attempting to access PHP webshells / backdoors for persistent access."},
    13: {"cluster_label": "Legitimate application traffic", "label_conf": 0.598, "matched_patterns": "^/assets/, index-C0S0yCUQ\\.js", "secondary_labels": "Secrets discovery (.env harvesting); Cloud metadata / config exposure", "severity": "INFO", "severity_rank": 4, "jira_priority": None, "jira_description": None},
    14: {"cluster_label": "IoT / embedded device exploit scan", "label_conf": 0.220, "matched_patterns": "/bins/, HNAP0, device\\.rsp, goform/formJsonAjaxReq", "secondary_labels": "Exchange / Autodiscover / RDP probe; GeoServer / infrastructure admin probe", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Exploitation attempts targeting IoT and embedded device admin interfaces (routers, cameras, Hikvision)."},
    15: {"cluster_label": "Uncategorized / miscellaneous scanning", "label_conf": 0.000, "matched_patterns": "", "secondary_labels": "", "severity": "LOW", "severity_rank": 3, "jira_priority": "Low", "jira_description": None},
    16: {"cluster_label": "IoT / embedded device exploit scan", "label_conf": 0.202, "matched_patterns": "/bins/, HNAP0, apply\\.cgi, goform/Mail_Test", "secondary_labels": "Cloud metadata / config exposure; Exchange / Autodiscover / RDP probe", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Exploitation attempts targeting IoT and embedded device admin interfaces (routers, cameras, Hikvision)."},
    17: {"cluster_label": "IoT / embedded device exploit scan", "label_conf": 0.023, "matched_patterns": "GponForm/diag_Form, goform/formJsonAjaxReq, vp", "secondary_labels": "Cisco / VPN / firewall probe", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Exploitation attempts targeting IoT and embedded device admin interfaces (routers, cameras, Hikvision)."},
    18: {"cluster_label": "Secrets discovery (.env harvesting)", "label_conf": 0.851, "matched_patterns": "\\.env(\\.|$)", "secondary_labels": "PHP webshell deployment / backdoor probe; PHP info/config discovery", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Systematic harvesting of .env files to extract API keys, DB credentials, and secrets."},
    19: {"cluster_label": "Secrets discovery (.env harvesting)", "label_conf": 0.190, "matched_patterns": "\\.env(\\.|$)", "secondary_labels": "Cisco / VPN / firewall probe; SonicWall SSLVPN probe", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Systematic harvesting of .env files to extract API keys, DB credentials, and secrets."},
    20: {"cluster_label": "Secrets discovery (.env harvesting)", "label_conf": 0.496, "matched_patterns": "\\.env(\\.|$)", "secondary_labels": "PHP webshell deployment / backdoor probe; Cloud metadata / config exposure", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Systematic harvesting of .env files to extract API keys, DB credentials, and secrets."},
    21: {"cluster_label": "WordPress exploitation / admin enumeration", "label_conf": 1.000, "matched_patterns": "^/wp-admin\\b, ^/wp-includes\\b, ^/wp-login\\.php$", "secondary_labels": "PHP webshell deployment / backdoor probe; ACME challenge path abuse / odd probe", "severity": "HIGH", "severity_rank": 1, "jira_priority": "High", "jira_description": "Attacker is actively enumerating WordPress admin paths and attempting to exploit WP core files."},
}

# HDBSCAN historical cluster summary (static system context, loaded once)
HDBSCAN_CLUSTERS_AFTER_TRAINING = """
Cluster -1 | n=972   Top paths: /api/auth/login 1842, / 626, /favicon.ico 107  Avg req: 8.09  Avg 4xx: 0.008
Cluster 0  | n=56    Top paths: /cgi-bin/.%0e/...bin/sh 47, google.com:0 34     Avg req: 1.59  Avg 4xx: 0.0
Cluster 1  | n=75    Top paths: /.git/config 92, /geoserver/web/ 33, /.env 13   Avg req: 2.31  Avg 4xx: 0.0
Cluster 2  | n=97    Top paths: /login 63, /remote/login 22, /login.html 17     Avg req: 2.20  Avg 4xx: 0.0
Cluster 3  | n=73    Top paths: /favicon.ico 71, / 30                           Avg req: 1.79  Avg 4xx: 0.0
Cluster 4  | n=60    Top paths: /favicon.ico 133, / 58, /robots.txt 5           Avg req: 3.43  Avg 4xx: 0.0
Cluster 5  | n=60    Top paths: /robots.txt 86, /favicon.ico 21                 Avg req: 2.47  Avg 4xx: 0.0
Cluster 6  | n=61    Top paths: / 228, /service.web 4                           Avg req: 3.80  Avg 4xx: 0.0
Cluster 7  | n=97    Top paths: / 61, /ms.php 3, /lite.php 3                    Avg req: 1.00  Avg 4xx: 0.0
Cluster 8  | n=69    Top paths: / 120, /check_health 4, /.streamlit/secrets 2   Avg req: 2.00  Avg 4xx: 0.0
Cluster 9  | n=76    Top paths: / 136, /developmentserver/metadatauploader 6    Avg req: 2.00  Avg 4xx: 0.0
Cluster 10 | n=84    Top paths: / 160, /wp-admin.php 2                          Avg req: 2.00  Avg 4xx: 0.0
Cluster 11 | n=133   Top paths: / 116, /RDWeb/Pages/en-US/login.aspx 2          Avg req: 1.02  Avg 4xx: 0.0
Cluster 12 | n=50    Top paths: /wp-content/themes/admin.php 7, /admin.php 6    Avg req: 2.36  Avg 4xx: 0.0
Cluster 13 | n=76    Top paths: / 115, /assets/index-C0S0yCUQ.js 67             Avg req: 5.46  Avg 4xx: 0.0
Cluster 14 | n=201   Top paths: / 352, /developmentserver 10, /bins/ 8          Avg req: 2.00  Avg 4xx: 0.0
Cluster 15 | n=101   Top paths: / 196, ip.ninonakano.jp:0 4                     Avg req: 2.00  Avg 4xx: 0.0
Cluster 16 | n=232   Top paths: / 199, /cdn-cgi/trace 11, /bins/ 6              Avg req: 1.00  Avg 4xx: 0.0
Cluster 17 | n=129   Top paths: / 123, ip.ninonakano.jp:0 2                     Avg req: 1.00  Avg 4xx: 0.0
Cluster 18 | n=85    Top paths: /api/.env 14, /api/info.php 12                  Avg req: 1.93  Avg 4xx: 0.0
Cluster 19 | n=63    Top paths: / 27, /api/.env 19, /api/sonicos 16             Avg req: 38.27 Avg 4xx: 0.387
Cluster 20 | n=396   Top paths: / 3928, /v0/.env 210, /.env 172                 Avg req: 68.79 Avg 4xx: 0.002
Cluster 21 | n=60    Top paths: /wp-admin/classwithtostring.php 62              Avg req: 14.4  Avg 4xx: 0.0
"""

ANALYST_PROMPT = """
You are a senior cybersecurity analyst writing WAF rules for Cloudflare Free tier.

## INPUTS
1. HISTORICAL_CLUSTER_CONTEXT — reference only. Do NOT use as basis for recommendations.
2. CURRENT_ROLLUP — the ONLY source of truth. Contains clusters detected in the last 5 minutes.
3. CURRENT_PREDICTIONS — raw rows; use only to enrich CURRENT_ROLLUP context.
4. CLUSTER_SEVERITY_LEVELS — maps cluster IDs to labels, severity, and Jira priority.

## YOUR TASK
Analyze CURRENT_ROLLUP and output a concise WAF response structured as follows:

**Threat Summary** (1 sentence): What is being attacked and how severe is it?

**Cloudflare Free Tier Actions** (bullet list):
- One action per detected cluster in CURRENT_ROLLUP
- Each action must reference the cluster ID and matched pattern
- Use only Cloudflare Free tier capabilities:
  * Firewall Rules (IP block, URI path match, country block)
  * Rate Limiting (free: 1 rule max)
  * IP Access Rules
  * Security Level adjustment (Under Attack Mode if CRITICAL)
- After each action, add 1 sentence explaining WHY this action was chosen for this cluster
- After the reasoning, add 1 relevant reference link (CVE, MITRE ATT&CK technique, or vendor advisory)

**Triage Priority**: List cluster IDs in order of severity_rank (lowest = highest priority).

## CLUSTER 13 — LEGITIMATE TRAFFIC (SPECIAL HANDLING)
Cluster 13 is known-good application traffic. Its normal fingerprint is:
- Top paths: /, /assets/*, /favicon.ico, /robots.txt
- Avg ratio_4xx: 0.0
- Avg request_count: ~5.5
- Label: Legitimate application traffic / INFO severity

IGNORE Cluster 13 in CURRENT_ROLLUP UNLESS you detect anomalous behaviour such as:
- /.env or secrets-harvesting paths appearing in its top paths
- ratio_4xx spiking above 0.05
- request_count increasing significantly beyond baseline (~5.5)
- Secondary labels shifting toward "Secrets discovery" or any CRITICAL/HIGH label

If any of the above are present in Cluster 13, FLAG IT explicitly at the top of your response:
⚠️ CLUSTER 13 ANOMALY: [describe what changed] — treat as "Secrets discovery (.env harvesting)" / HIGH severity.

## JIRA TICKETS
For every cluster in CURRENT_ROLLUP where CLUSTER_SEVERITY_LEVELS shows severity MEDIUM, HIGH, or CRITICAL,
call the create_jira_ticket tool using this exact structure:

**summary** format:
[Severity] Cluster <ID> — <short_label> (<top matched pattern>)
Example: [HIGH] Cluster 17 — IoT Device Exploit Scan (goform/formJsonAjaxReq)

**description** format — use EXACTLY this structure with bold headers *LIKE THIS*:

*THREAT*
<cluster_label> detected in the last 5 minutes.
Severity: <severity> | Jira Priority: <jira_priority>

*OBSERVED ACTIVITY*
- Top paths: <top 3 paths from CURRENT_ROLLUP>
- Matched patterns: <matched_patterns from CLUSTER_SEVERITY_LEVELS>
- Request volume: <request_count> requests | 4xx ratio: <ratio_4xx>

*WHY THIS WAS FLAGGED*
<1-2 sentences explaining what behaviour triggered this cluster and why it is a threat>

*RECOMMENDED WAF ACTION*
<specific Cloudflare Free tier action — IP block / URI block / rate limit / Under Attack Mode>

*REASONING*
<1-2 sentences explaining why this specific WAF action was chosen over alternatives>

*REFERENCES*
You must call query_knowledgebase before writing this section.
For each reference, cite the KB entry using: [KB-ID: <id>] <title> — <1 sentence summary>
Only include references you are certain exist. Prefer: attack.mitre.org, nvd.nist.gov, owasp.org
NEVER fabricate or guess URLs. Plain text reference is always better than a broken link.

**priority**: use the jira_priority value from CLUSTER_SEVERITY_LEVELS
**Skip** clusters with severity LOW, INFO, or where jira_priority is null.

## STRICT RULES
- Only act on clusters present in CURRENT_ROLLUP — nothing else.
- If a single cluster is present, output rules for that cluster only.
- Do not invent threats not present in CURRENT_ROLLUP.
- Do not recommend Cloudflare Pro/Business/Enterprise features.
- Be specific: reference matched_patterns and cluster labels directly.
- No filler, no preamble. Output the three sections only (plus Cluster 13 flag if triggered).
- NEVER output PII in tool requests or in the response.
- NEVER fabricate URLs. If unsure whether a URL exists, omit the link and write plain text only.

## DEBUGGING NOTE
For evaluation purposes:
- State which tool calls were made and for which cluster IDs
- If a ticket was skipped, state why (severity too low, null priority, etc.)
- State the resulting ticket ID
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledgebase",
            "description": (
                "Semantic search over the internal cybersecurity knowledgebase. "
                "Use this to look up CVEs, MITRE ATT&CK tactics, remediation guides, "
                "or threat intel relevant to a detected cluster or pattern."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query e.g. 'PHP webshell CVE remediation' or 'MITRE T1190'",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of KB entries to return (default 3)",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_jira_ticket",
            "description": "Create a JIRA security ticket for a detected attack cluster.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary":     {"type": "string"},
                    "description": {"type": "string"},
                    "priority":    {"type": "string", "enum": ["Highest", "High", "Medium", "Low"]},
                },
                "required": ["summary", "description"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Knowledgebase — load + embed with pickle cache
# ---------------------------------------------------------------------------

def _extract_str(val) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("@value", "")
    if isinstance(val, list) and val:
        return _extract_str(val[0])
    return ""


def load_kb_with_cache(
    kb_path: Path = KB_PATH,
    cache_path: Path = EMBED_CACHE_PATH,
) -> tuple[list[dict], np.ndarray]:
    """
    Load the knowledge base entries and their embedding vectors.
    Reads from pickle cache if available; otherwise embeds and saves cache.
    """
    if cache_path.exists():
        log.info("Loading KB embeddings from cache: %s", cache_path)
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        log.info("KB cache loaded: %d entries, dim=%d", len(cached["entries"]), cached["vectors"].shape[1])
        return cached["entries"], cached["vectors"]

    log.info("No cache found at %s — embedding KB from scratch (this takes ~1 min)", cache_path)
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)

    with open(kb_path, "r") as f:
        kb_raw = json.load(f)

    graph = kb_raw.get("@graph", [])
    kb_entries = []
    for node in graph:
        title   = _extract_str(node.get("rdfs:label", ""))
        content = _extract_str(node.get("d3f:definition", ""))
        if title and content:
            kb_entries.append({"id": node.get("@id", ""), "title": title, "content": content})

    kb_texts = [e["title"] + " " + e["content"] for e in kb_entries]

    all_vecs = []
    t0 = time()
    for i in range(0, len(kb_texts), EMBED_BATCH_SIZE):
        batch = kb_texts[i : i + EMBED_BATCH_SIZE]
        vecs  = np.array(vo.embed(batch, model=EMBED_MODEL, input_type="document").embeddings)
        all_vecs.append(vecs)
        if (i // EMBED_BATCH_SIZE) % 10 == 0:
            log.info("  Embedded %d/%d entries…", i + len(batch), len(kb_texts))

    kb_vectors = np.vstack(all_vecs)
    kb_vectors = kb_vectors / np.linalg.norm(kb_vectors, axis=1, keepdims=True)

    log.info("Embedding complete in %.1fs — saving cache to %s", time() - t0, cache_path)
    with open(cache_path, "wb") as f:
        pickle.dump({"entries": kb_entries, "vectors": kb_vectors}, f)

    log.info("KB index built: %d entries, dim=%d", len(kb_entries), kb_vectors.shape[1])
    return kb_entries, kb_vectors


# Module-level lazy singletons (loaded on first run_pipeline call)
_kb_entries: list[dict] | None = None
_kb_vectors: np.ndarray | None = None


def _ensure_kb_loaded():
    global _kb_entries, _kb_vectors
    if _kb_entries is None:
        _kb_entries, _kb_vectors = load_kb_with_cache()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def query_knowledgebase(query: str, top_k: int = 3) -> str:
    """Semantic search over the D3FEND/MITRE KB."""
    _ensure_kb_loaded()
    import voyageai
    vo = voyageai.Client(api_key=VOYAGE_API_KEY)
    q_vec = np.array(vo.embed([query], model=EMBED_MODEL, input_type="document").embeddings)[0]
    q_vec = q_vec / np.linalg.norm(q_vec)

    scores  = _kb_vectors @ q_vec
    top_idx = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in top_idx:
        if i < len(_kb_entries):
            e = _kb_entries[i]
            results.append(f"[KB-ID: {e['id']}] {e['title']}\nContent: {e['content']}")
    return "\n\n---\n\n".join(results)


def create_jira_ticket(summary: str, description: str, priority: str = "Medium") -> dict:
    """Create a JIRA ticket and return the issue key."""
    url  = JIRA_REQUEST_URL
    auth = HTTPBasicAuth(JIRA_AUTH_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Bug"},
            "priority":  {"name": priority},
            "labels":    ["honeypot", "automated"],
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, auth=auth)
        resp.raise_for_status()
        key = resp.json().get("key")
        log.info("✓ Jira ticket created: %s", key)
        return {"key": key}
    except requests.exceptions.RequestException as e:
        log.error("✗ Failed to create Jira ticket: %s", e)
        return {}


def _get_cloudflare_waf_rules() -> list:
    """Fetch current Cloudflare WAF firewall rules."""
    firewall_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/firewall/rules"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    try:
        resp = requests.get(firewall_url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except requests.exceptions.RequestException as e:
        log.warning("Could not fetch Cloudflare WAF rules: %s", e)
        return []


def _dispatch_tool(call) -> str:
    args = json.loads(call.function.arguments)
    if call.function.name == "query_knowledgebase":
        return query_knowledgebase(**args)
    elif call.function.name == "create_jira_ticket":
        args.setdefault("priority", "Medium")
        return json.dumps(create_jira_ticket(**args))
    return json.dumps({"error": "unknown tool"})


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    rollup_payload: str,
    pred_csv_path: str | None = None,
    pred_df: pd.DataFrame | None = None,
    hdbscan_context: str = HDBSCAN_CLUSTERS_AFTER_TRAINING,
    cluster_severity_dict: dict = CLUSTER_SEVERITY_DICT,
    groq_model: str = GROQ_MODEL,
    rebuild_cache: bool = False,
) -> str:
    """
    Run the agentic LLM threat analysis pipeline.

    Parameters
    ----------
    rollup_payload       : JSON string produced by the clustering model
    pred_csv_path        : Path to the pred CSV file (or pass pred_df directly)
    pred_df              : Pre-loaded predictions DataFrame (takes priority over path)
    hdbscan_context      : Historical cluster summary string (default: training-time reference)
    cluster_severity_dict: Cluster ID → severity/label/jira mapping
    groq_model           : Groq model name
    rebuild_cache        : If True, delete existing embedding cache and re-embed

    Returns
    -------
    str : Final LLM response text
    """
    from groq import Groq

    # --- Optionally rebuild cache ---
    if rebuild_cache and EMBED_CACHE_PATH.exists():
        log.info("Removing existing embedding cache for rebuild")
        EMBED_CACHE_PATH.unlink()

    # --- Ensure embeddings are ready ---
    _ensure_kb_loaded()

    # --- Load predictions ---
    if pred_df is None:
        if pred_csv_path is None:
            raise ValueError("Must provide either pred_csv_path or pred_df")
        pred_df = pd.read_csv(pred_csv_path)

    pred_cols = [
        "client_ip", "window_start", "request_count", "unique_paths", "unique_methods",
        "status_200", "status_401", "status_403", "status_404", "status_429", "status_500",
        "ratio_4xx", "ratio_429", "ratio_5xx", "path_text", "cluster", "cluster_strength", "uas",
    ]
    # Keep only columns that exist (graceful if schema differs slightly)
    available = [c for c in pred_cols if c in pred_df.columns]
    pred_str = pred_df[available].to_string(index=False)

    # --- Fetch live WAF rules ---
    current_waf_rules = _get_cloudflare_waf_rules()

    # --- Build messages ---
    messages = [
        {"role": "system", "content": f"HISTORICAL_CLUSTER_CONTEXT:\n{hdbscan_context}"},
        {"role": "system", "content": f"CURRENT_ROLLUP:\n{rollup_payload}"},
        {"role": "system", "content": f"CURRENT_PREDICTIONS:\n{pred_str}"},
        {"role": "system", "content": f"CLUSTER-SEVERITY-LEVELS:\n{json.dumps(cluster_severity_dict, indent=2)}"},
        {"role": "system", "content": f"CURRENT_CLOUDFLARE_WAF_RULES:\n{json.dumps(current_waf_rules, indent=2)}"},
        {"role": "user",   "content": ANALYST_PROMPT},
    ]

    client = Groq(api_key=GROQ_API_KEY)
    force_finish = False

    for iteration in range(MAX_TOOL_ITERS):
        completion = client.chat.completions.create(
            model=groq_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="none" if force_finish else "auto",
            stream=False,
        )

        msg = completion.choices[0].message

        if msg.tool_calls and not force_finish:
            messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
            for call in msg.tool_calls:
                log.info("Tool call: %s | args: %s", call.function.name, call.function.arguments[:120])
                result = _dispatch_tool(call)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                })
                if call.function.name == "create_jira_ticket":
                    force_finish = True
        else:
            log.info("Pipeline complete after %d iterations", iteration + 1)
            return msg.content

    log.warning("Reached MAX_TOOL_ITERS (%d) without a final response", MAX_TOOL_ITERS)
    return ""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run LLM cybersecurity threat analysis pipeline")
    parser.add_argument("--rollup",  required=True, help="Path to rollup JSON file (or inline JSON string)")
    parser.add_argument("--pred",    required=True, help="Path to pred CSV file")
    parser.add_argument("--rebuild-cache", action="store_true", help="Force re-embed KB (ignore existing cache)")
    args = parser.parse_args()

    # Accept either a file path or a raw JSON string for --rollup
    rollup_path = Path(args.rollup)
    if rollup_path.exists():
        rollup_payload = rollup_path.read_text()
    else:
        rollup_payload = args.rollup  # treat as inline JSON string

    result = run_pipeline(
        rollup_payload=rollup_payload,
        pred_csv_path=args.pred,
        rebuild_cache=args.rebuild_cache,
    )
    print(result)


if __name__ == "__main__":
    main()