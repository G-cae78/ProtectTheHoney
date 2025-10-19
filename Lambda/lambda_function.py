import json
import base64
from datetime import datetime
from urllib.parse import parse_qs

def debug_print_event(event):
    # Print a compact summary plus the body for debugging
    try:
        print("RAW EVENT:")
        print(json.dumps(event, indent=2, default=str))
    except Exception:
        print("Could not pretty-print event; printing repr:")
        print(repr(event))

def safe_decode_body(event):
    body = event.get("body")
    if not body:
        return None

    # If body is base64 encoded, decode it
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body).decode("utf-8", errors="ignore")
        except Exception as e:
            print("⚠️ base64 decode failed:", e)
            # leave body as-is

    return body

def try_parse_json(body):
    """Try to parse JSON. If the parsed result is a string (JSON-in-string),
       try loading again."""
    if not body:
        return None
    try:
        parsed = json.loads(body)
        # If parsed is a string (e.g. '"{...}"'), try parse again
        if isinstance(parsed, str):
            try:
                parsed2 = json.loads(parsed)
                return parsed2
            except Exception:
                return parsed  # fallback: raw string
        return parsed
    except Exception as e:
        # not valid JSON
        # print("JSON parse failed:", e)
        return None

def parse_form_encoded(body):
    try:
        parsed_qs = parse_qs(body, keep_blank_values=True)
        # parse_qs returns lists for each key
        simplified = {k: v[0] if isinstance(v, list) and v else None for k, v in parsed_qs.items()}
        return simplified
    except Exception as e:
        print("Form parse failed:", e)
        return None

def extract_fields_from_event(event):
    # Try multiple sources for username/password/email
    # 1. query string parameters
    qsp = event.get("queryStringParameters") or event.get("query") or {}
    if qsp:
        username = qsp.get("username") or qsp.get("email") or qsp.get("user")
        password = qsp.get("password")
        if username or password:
            return {"username": username, "password": password, "email": qsp.get("email")}

    # 2. body parsing
    raw_body = safe_decode_body(event)
    print("Debuuggerrrr")
    if raw_body:
        # try JSON first
        parsed_json = try_parse_json(raw_body)
        if isinstance(parsed_json, dict):
            return {
                "username": parsed_json.get("username") or parsed_json.get("email") or parsed_json.get("user"),
                "password": parsed_json.get("password"),
                "email": parsed_json.get("email")
            }

        # if json parse returned a string (rare), we already attempted double-parse in try_parse_json
        # try form-urlencoded
        parsed_form = parse_form_encoded(raw_body)
        if parsed_form:
            return {
                "username": parsed_form.get("username") or parsed_form.get("email") or parsed_form.get("user"),
                "password": parsed_form.get("password"),
                "email": parsed_form.get("email")
            }

        # fallback: search for username/password tokens in raw text (simple)
        lower = raw_body.lower()
        u = None
        p = None
        for token in ("username=", "user=", "email="):
            if token in lower:
                try:
                    # naive extraction
                    k = lower.split(token, 1)[1].split("&", 1)[0]
                    u = k
                    break
                except Exception:
                    pass
        if "password=" in lower and not p:
            try:
                p = lower.split("password=", 1)[1].split("&", 1)[0]
            except Exception:
                pass
        if u or p:
            return {"username": u, "password": p, "email": None}

    # 3. if nothing, return None
    return {"username": None, "password": None, "email": None}

def handler(event, context):
    # Debug print raw event for first-time inspection
    print("🔔 New event received: ",event)
    debug_print_event(event)

    # Handle CORS preflight (OPTIONS)
    http_method = event.get("httpMethod") or (event.get("requestContext") or {}).get("http", {}).get("method")
    if http_method and http_method.upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": ""
        }

    timestamp = datetime.utcnow().isoformat()

    # request context / headers
    request_context = event.get("requestContext", {}) or {}
    http_info = request_context.get("http", {}) or {}
    source_ip = (
        http_info.get("sourceIp")
        or request_context.get("identity", {}).get("sourceIp")
        or event.get("requestContext", {}).get("identity", {}).get("sourceIp")
        or event.get("requestContext", {}).get("http", {}).get("sourceIp")
        or None
    )
    headers = event.get("headers") or {}
    user_agent = headers.get("User-Agent") or headers.get("user-agent")

    # extract username/password/email robustly
    cred = extract_fields_from_event(event)
    username = cred.get("username")
    password = cred.get("password")
    email = cred.get("email")

    record = {
        "timestamp": timestamp,
        "source_ip": source_ip,
        "user_agent": user_agent,
        "method": (http_method or event.get("httpMethod") or "UNKNOWN"),
        "path": event.get("rawPath") or event.get("path") or "/",
        "username": username,
        "password": password,
        "email": email,
        "headers": headers
    }

    print("🐝 Honeypot Access Detected (parsed):")
    print(json.dumps(record, indent=2, default=str))

    # Return response with CORS headers so browser won't block
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps({"message": "Received"})
    }

