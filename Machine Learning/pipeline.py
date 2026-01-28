# pipeline.py
import re
import pandas as pd
import numpy as np
from scipy.sparse import hstack, csr_matrix
from hdbscan.prediction import approximate_predict

REQ_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP\/")

def parse_request(line: str):
    line = str(line)
    m = REQ_RE.search(line)
    if not m:
        return ("UNK", "/")
    method = m.group("method")
    path = m.group("path").split("?")[0]
    path = re.sub(r"\d+", "0", path)  # normalize digits like you did
    return method, path

def load_csv_like_yours(csv_path: str) -> pd.DataFrame:
    cols = [
        "Log Source and Client IP",
        "Identd identity",
        "Authenticated User",
        "Timestamp",
        "HTTP Request Line",
        "HTTP Status Code",
        "Response size (bytes)",
        "Referer Header",
        "User-Agent",
    ]
    df = pd.read_csv(csv_path, names=cols, header=None)

    df["client_ip"] = df["Log Source and Client IP"].astype(str).str.split(":").str[-1]

    df["Timestamp"] = df["Timestamp"].astype(str).str.strip("[] ")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%d/%b/%Y:%H:%M:%S", errors="coerce")
    df["Timestamp"] = df["Timestamp"].dt.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT")

    df["HTTP Status Code"] = pd.to_numeric(df["HTTP Status Code"], errors="coerce")
    df["Response size (bytes)"] = pd.to_numeric(df["Response size (bytes)"], errors="coerce").fillna(0)

    df[["http_method", "http_path"]] = df["HTTP Request Line"].apply(lambda x: pd.Series(parse_request(x)))
    return df.dropna(subset=["Timestamp", "client_ip"])

def make_5min_windows(df: pd.DataFrame) -> pd.DataFrame:
    # floor timestamps to 5-min buckets
    df["window_start"] = df["Timestamp"].dt.floor("5min")

    # status features (match what you trained on)
    for code in [401, 403, 404, 429]:
        df[f"is_{code}"] = (df["HTTP Status Code"] == code).astype(int)

    grouped = (
        df.groupby(["client_ip", "window_start"])
          .agg(
              request_count=("http_path", "size"),
              unique_paths=("http_path", pd.Series.nunique),
              unique_methods=("http_method", pd.Series.nunique),

              status_401=("is_401", "sum"),
              status_403=("is_403", "sum"),
              status_404=("is_404", "sum"),
              status_429=("is_429", "sum"),

              avg_response_size=("Response size (bytes)", "mean"),
              std_response_size=("Response size (bytes)", "std"),

              paths=("http_path", list),
              methods=("http_method", list),
              uas=("User-Agent", list),
          )
          .reset_index()
    )

    grouped["std_response_size"] = grouped["std_response_size"].fillna(0)
    grouped["ratio_4xx"] = (grouped["status_401"] + grouped["status_403"] + grouped["status_404"]) / grouped["request_count"].clip(lower=1)
    grouped["ratio_429"] = grouped["status_429"] / grouped["request_count"].clip(lower=1)

    grouped["path_text"] = grouped["paths"].apply(lambda xs: " ".join(xs))
    return grouped

def build_X(windows: pd.DataFrame, vectorizer, scaler, num_cols):
    X_txt = vectorizer.transform(windows["path_text"].fillna(""))
    X_num = scaler.transform(windows[num_cols].fillna(0))
    return hstack([X_txt, csr_matrix(X_num)])

def predict(windows: pd.DataFrame, X, hdb):
    labels, strengths = approximate_predict(hdb, X)
    out = windows.copy()
    out["cluster"] = labels
    out["cluster_strength"] = strengths
    return out
