import pandas as pd
import json
import requests

def send_batch(rollup_pred_pairs: list[tuple[dict, str]]):
    """
    rollup_pred_pairs: list of (rollup_dict, pred_csv_path) tuples
    """
    items = []
    cols  = ["client_ip", "cluster", "uas", "path_text",
             "request_count", "ratio_4xx", "cluster_strength"]

    for rollup, pred_csv_path in rollup_pred_pairs:
        cluster_ids = [c["cluster"] for c in rollup["clusters"]]
        df          = pd.read_csv(pred_csv_path)
        df_filtered = df[df["cluster"].isin(cluster_ids)]
        predictions = df_filtered[cols].to_dict(orient="records")

        items.append({
            "rollup":      rollup,
            "predictions": predictions,
        })

    r = requests.post(
        "http://localhost:8000/pipeline/rollup/batch",
        json={"items": items},
        headers={
            "Content-Type":      "application/json",
            "x-pipeline-secret": "your-secret-here",
        },
        timeout=300,  # batch can take longer
    )
    return r.json()

# Usage
result = send_batch([
    (rollup_payload_1_dict, "pred_20260319T135002Z.csv"),
    (rollup_payload_2_dict, "pred_20260319T140002Z.csv"),
    (rollup_payload_3_dict, "pred_20260319T145002Z.csv"),
])
print(result["summary"])