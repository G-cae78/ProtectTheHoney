import re
import pandas as pd
from scipy.sparse import hstack, csr_matrix
from hdbscan.prediction import approximate_predict

REQ_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP\/")

def parse_request(req_line: str):
    req_line = str(req_line)
    m = REQ_RE.search(req_line)
    if not m:
        return ("UNK", "/")
    method = m.group("method")
    path = m.group("path").split("?")[0]
    path = re.sub(r"\d+", "0", path)
    return method, path

def load_csv_logs(csv_path: str) -> pd.DataFrame:
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

    df["client_ip"] = df["Log Source and Client IP"].astype(str).str.split(":").str[-1].str.strip()

    ts = df["Timestamp"].astype(str).str.strip("[] ").str.strip()
    df["Timestamp"] = pd.to_datetime(ts, format="%d/%b/%Y:%H:%M:%S", errors="coerce", utc=True)

    df["HTTP Status Code"] = pd.to_numeric(df["HTTP Status Code"], errors="coerce")
    df["Response size (bytes)"] = pd.to_numeric(df["Response size (bytes)"], errors="coerce").fillna(0)

    df[["http_method", "http_path"]] = df["HTTP Request Line"].apply(lambda x: pd.Series(parse_request(x)))
    df = df.dropna(subset=["Timestamp", "client_ip", "HTTP Status Code"])
    return df

def make_5min_windows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["window_start"] = df["Timestamp"].dt.floor("5min")

    for code in [200, 401, 403, 404, 429, 500]:
        df[f"is_{code}"] = (df["HTTP Status Code"] == code).astype(int)
        agg = (
        df.groupby(["client_ip", "window_start"])
        .agg(
            request_count=("http_path", "size"),
            unique_paths=("http_path", pd.Series.nunique),
            unique_methods=("http_method", pd.Series.nunique),

            status_200=("is_200", "sum"),
            status_401=("is_401", "sum"),
            status_403=("is_403", "sum"),
            status_404=("is_404", "sum"),
            status_429=("is_429", "sum"),
            status_500=("is_500", "sum"),

            avg_response_size=("Response size (bytes)", "mean"),
            std_response_size=("Response size (bytes)", "std"),

            paths=("http_path", list),
            uas=("User-Agent", list),
        )
        .reset_index()
    )

    agg["std_response_size"] = agg["std_response_size"].fillna(0)

    denom = agg["request_count"].clip(lower=1)
    agg["ratio_4xx"] = (agg["status_401"] + agg["status_403"] + agg["status_404"]) / denom
    agg["ratio_429"] = agg["status_429"] / denom
    agg["ratio_5xx"] = agg["status_500"] / denom

    agg["path_text"] = agg["paths"].apply(lambda xs: " ".join(map(str, xs)))
    return agg

def build_X(windows: pd.DataFrame, vectorizer, scaler, num_cols):
    X_txt = vectorizer.transform(windows["path_text"].fillna(""))
    X_num = scaler.transform(windows[num_cols].fillna(0))
    return hstack([X_txt, csr_matrix(X_num)])

def predict_windows(windows: pd.DataFrame, X, hdb):
    labels, strengths = approximate_predict(hdb, X)
    out = windows.copy()
    out["cluster"] = labels
    out["cluster_strength"] = strengths
    return out
# Nginx combined-ish log line example:
# 1.2.3.4 - - [28/Jan/2026:12:34:56 +0000] "GET /path HTTP/1.1" 404 123 "-" "UA..."
NGINX_RE = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+"(?P<req>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)'
    r'(?:\s+"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)")?'
)

def parse_nginx_lines(lines):
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = NGINX_RE.match(line)
        if not m:
            continue

        ip = m.group("ip")
        ts_raw = m.group("ts")  # e.g. 28/Jan/2026:12:34:56 +0000
        req = m.group("req")
        status = int(m.group("status"))
        size_raw = m.group("size")
        ua = m.group("ua") or ""

        ts = pd.to_datetime(ts_raw, format="%d/%b/%Y:%H:%M:%S %z", errors="coerce", utc=True)
        if pd.isna(ts):
            continue

        size = int(size_raw) if str(size_raw).isdigit() else 0

        method, path = parse_request(req)

        rows.append({
            "client_ip": ip,
            "Timestamp": ts,
            "HTTP Status Code": status,
            "Response size (bytes)": size,
            "http_method": method,
            "http_path": path,
            "User-Agent": ua,
        })

    return pd.DataFrame(rows)