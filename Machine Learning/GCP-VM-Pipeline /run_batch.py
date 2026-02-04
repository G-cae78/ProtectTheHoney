import os
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

import numpy as np
import joblib
import pandas as pd

from pipeline import parse_nginx_lines, make_5min_windows, build_X, predict_windows

BASE = Path("/opt/honey")
ART = BASE / "artifacts"
STATE = BASE / "state"
RESULTS = BASE / "results"
LOGS = BASE / "logs"

STATE.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

ACCESS_LOG = Path("/var/log/nginx/access.log")
OFFSET_FILE = STATE / "nginx_access.offset"

def read_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except:
            return 0
    return 0

def write_offset(off: int):
    OFFSET_FILE.write_text(str(off))

def read_new_lines():
    if not ACCESS_LOG.exists():
        raise FileNotFoundError(f"Missing {ACCESS_LOG}")

    last_off = read_offset()
    size = ACCESS_LOG.stat().st_size

    # logrotate or truncation: if file shrank, reset offset
    if size < last_off:
        last_off = 0

    with open(ACCESS_LOG, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(last_off)
        data = f.read()
        new_off = f.tell()
    write_offset(new_off)
    lines = data.splitlines()
    return lines

def main():
    # Load artifacts
    print("RUN", datetime.now(timezone.utc).isoformat())
    hdb = joblib.load(ART / "hdbscan.joblib")
    tfidf = joblib.load(ART / "tfidf.joblib")
    scaler = joblib.load(ART / "scaler.joblib")
    num_cols = joblib.load(ART / "num_cols.joblib")

    lines = read_new_lines()
    if not lines:
        print("No new nginx lines")
        return

    df = parse_nginx_lines(lines)
    if df.empty:
        return

    windows = make_5min_windows(df)
    if windows.empty:
        return

    missing = [c for c in num_cols if c not in windows.columns]
    if missing:
        raise RuntimeError(f"Missing numeric feature columns: {missing}")

    X = build_X(windows, tfidf, scaler, num_cols)
    # --- Attach to existing clusters using cosine NN (preserves notebook pipeline) ---
    nn_index = joblib.load(ART / "nn_index.joblib")
    labels_train = joblib.load(ART / "labels_train.joblib")

    # distance is cosine distance in [0..2], similarity = 1 - distance (usually ~0..1)
    dist, idx = nn_index.kneighbors(X, n_neighbors=1, return_distance=True)
    idx = idx.ravel()
    dist = dist.ravel()

    assigned = labels_train[idx].copy()
    strength = 1.0 - dist  # higher = more similar

    # PERCENTILE-BASED THRESHOLDING: mark top X% farthest points as noise (-1)
    # (same approach as notebook: keep bottom 85% by distance, mark top 15% as noise)
    PERCENTILE_THRESHOLD = 85
    dist_threshold = np.percentile(dist, PERCENTILE_THRESHOLD)
    
    assigned = [int(a) if d <= dist_threshold else -1 for a, d in zip(assigned, dist)]

    pred = windows.copy()
    pred["cluster"] = assigned
    pred["cluster_strength"] = strength
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pred_path = RESULTS / f"pred_{now}.csv"
    pred.to_csv(pred_path, index=False)

    # rollup json (for LLM later)
    # Load cluster label/severity mapping
    cluster_map_path = ART / "cluster_map.json"
    cluster_map = {}
    if cluster_map_path.exists():
        cluster_map = json.loads(cluster_map_path.read_text())
    roll = []
    for cluster_id, g in pred.groupby("cluster"):
        all_paths = [p for paths in g["paths"] for p in paths]
        top_paths = pd.Series(all_paths).value_counts().head(10).to_dict()
        cid = int(cluster_id)
    meta = cluster_map.get(str(cid), cluster_map.get("-1", {"label": "Unknown", "severity": "Investigate"}))

    roll.append({
        "cluster": cid,
        "cluster_label": meta.get("label", "Unknown"),
        "severity": meta.get("severity", "Investigate"),
        "patterns": meta.get("patterns", []),
            "windows": int(len(g)),
            "avg_strength": float(g["cluster_strength"].mean()),
            "top_paths": top_paths,
            "status_totals": {
                "200": int(g["status_200"].sum()),
                "401": int(g["status_401"].sum()),
                "403": int(g["status_403"].sum()),
                "404": int(g["status_404"].sum()),
                "429": int(g["status_429"].sum()),
                "500": int(g["status_500"].sum()),
            }
        })

    roll_path = RESULTS / f"rollup_{now}.json"
    total_windows = int(len(pred))
    noise_windows = int((pred["cluster"] == -1).sum())
    noise_rate = float(noise_windows / total_windows) if total_windows else 0.0
    avg_strength_all = float(pred["cluster_strength"].mean()) if total_windows else 0.0

    roll_path.write_text(json.dumps({
        "generated_at": now,
        "source": str(ACCESS_LOG),
        "summary": {
            "total_windows": total_windows,
            "noise_windows": noise_windows,
            "noise_rate": noise_rate,
            "avg_strength": avg_strength_all
            },
       "clusters": roll
    }, indent=2))


if __name__ == "__main__":
    main()