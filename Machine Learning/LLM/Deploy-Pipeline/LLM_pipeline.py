# ============================================================
# LLM_pipeline.py — FastAPI deployment
# ============================================================
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import asyncio
import uvicorn
import json
import os
import re
import numpy as np
import pickle
import hashlib
import requests
from pathlib import Path
from datetime import datetime, date
from collections import deque
from dotenv import load_dotenv
from groq import Groq, APIStatusError, APIConnectionError
from requests.auth import HTTPBasicAuth
from contextlib import asynccontextmanager
import voyageai

load_dotenv()

# Run pipeline: python LLM_pipeline.py     

# ── Config ────────────────────────────────────────────────────
CLOUDFLARE_API_TOKEN  = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID    = os.getenv("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
JIRA_API_TOKEN        = os.getenv("JIRA_API_TOKEN")
JIRA_AUTH_EMAIL       = os.getenv("JIRA_AUTH_EMAIL")
JIRA_REQUEST_URL      = os.getenv("JIRA_REQUEST_URL")
JIRA_PROJECT_KEY      = os.getenv("JIRA_PROJECT_KEY")
GROQ_API_KEY          = os.getenv("GROQ_API_KEY")
VOYAGE_API_KEY        = os.getenv("VOYAGE_API_KEY")
PIPELINE_SECRET       = os.getenv("PIPELINE_SECRET")

CF_PHASE     = "http_request_firewall_custom"
CF_PHASE_URL = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/rulesets/phases/{CF_PHASE}/entrypoint"
CF_HEADERS   = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type":  "application/json"
}

MAX_EXPRESSION_LENGTH = 4096
RULE_BUDGET           = 5

''' 
List of LLM models to try for inference, in order of preference. 
The pipeline will attempt to use the first model and fall back to the next if there are issues (e.g., rate limits, errors). 
This allows for flexibility in case certain models are unavailable or encounter problems during processing.'
'''
MODELS = [
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

# ── Session state ─────────────────────────────────────────────
handled_clusters  = set()
deployed_patterns = {
    "block":             set(),
    "managed_challenge": set(),
    "js_challenge":      set(),
    "challenge":         set(),
}
session_date = datetime.now().date()
groq_client  = Groq(api_key=GROQ_API_KEY)
vo           = voyageai.Client(api_key=VOYAGE_API_KEY)

# ── KB setup ──────────────────────────────────────────────────
CACHE_PATH = Path("kb_embeddings.pkl")
kb_entries: list = []
kb_vectors        = None

def load_kb():
    global kb_entries, kb_vectors
    if not CACHE_PATH.exists():
        raise RuntimeError("kb_embeddings.pkl not found — run notebook KB setup cell first")
    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    kb_entries = cache["entries"]
    kb_vectors = cache["vectors"]
    print(f"✓ KB loaded: {len(kb_entries)} entries")

# ── FastAPI app and routes ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    load_kb() # load KB embeddings into memory on startup
    sync_deployed_patterns() # sync deployed patterns with Cloudflare on startup
    print("✓ Pipeline ready")
    yield

# ── FastAPI app ───────────────────────────────────────────────
app = FastAPI(title="Honey In The Cloud LLM Pipeline", lifespan=lifespan)

class RollupPayload(BaseModel):
    rollup:      dict # the rollup JSON containing cluster info and metadata
    predictions: list[dict] | None = None # optional list of prediction dicts (e.g., from pred.csv) to provide additional context for the LLM

def verify_secret(x_pipeline_secret: str = Header(...)):
    if x_pipeline_secret != PIPELINE_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorised")

# ── Routes ────────────────────────────────────────────────────
@app.get("/health")
def health(): # simple health check endpoint to verify the service is running
    return {
        "status":            "ok",
        "kb_entries":        len(kb_entries),
        "handled_clusters":  list(handled_clusters),
        "session_date":      str(session_date),
        "deployed_patterns": {k: len(v) for k, v in deployed_patterns.items()},
    }

@app.post("/pipeline/rollup", dependencies=[Depends(verify_secret)])
async def process_rollup(payload: RollupPayload): # main endpoint to process a single rollup with optional predictions, determine actionable clusters, and run the pipeline
    maybe_reset_session()

    rollup   = payload.rollup # the rollup JSON containing cluster info and metadata
    clusters = rollup.get("clusters", []) # list of clusters from the rollup, each containing details like cluster ID, label, severity, patterns, etc.

    actionable_severities = {"CRITICAL", "HIGH", "MEDIUM"} # define which severity levels are considered actionable for further processing (e.g., creating tickets, deploying rules)
    actionable = [] # list to hold clusters that are deemed actionable based on their severity and whether they've been handled before
    for c in clusters:
        severity = _get_cluster_severity(c["cluster"])
        print(f"  Cluster {c['cluster']} severity: {severity}") # log the severity of each cluster for visibility
        if severity in actionable_severities and c["cluster"] not in handled_clusters: # check if the cluster's severity is actionable and if it hasn't been handled in this session
            actionable.append(c)

    print(f"  Actionable clusters: {[c['cluster'] for c in actionable]}")
    print(f"  Handled clusters:    {handled_clusters}")

    if not actionable: # if there are no actionable clusters, skip processing and return a response indicating that the rollup was skipped due to no new actionable clusters
        return {
            "status":   "skipped",
            "reason":   "no new actionable clusters",
            "clusters": [c["cluster"] for c in clusters],
            }

    current_WAF_rules = _fetch_current_waf_rules() # fetch the current WAF rules from Cloudflare to provide context for the pipeline and ensure that any new rules deployed do not conflict with existing ones
    sync_deployed_patterns() # sync the in-memory record of deployed patterns with Cloudflare to ensure the pipeline has an up-to-date view of what patterns have already been deployed as rules

    result = await run_pipeline(
        rollup=rollup, 
        current_WAF_rules=current_WAF_rules, 
        predictions=payload.predictions)

    for c in actionable:
        handled_clusters.add(c["cluster"])

    return result

@app.post("/pipeline/reset", dependencies=[Depends(verify_secret)])
def reset_session():
    global handled_clusters
    handled_clusters = set()
    sync_deployed_patterns()
    return {"status": "reset", "deployed_patterns": {k: len(v) for k, v in deployed_patterns.items()}}

@app.delete("/pipeline/rules/auto", dependencies=[Depends(verify_secret)])
def delete_auto_rules_route():
    delete_all_auto_rules()
    return {"status": "deleted"}

@app.get("/pipeline/rules", dependencies=[Depends(verify_secret)])
def list_rules():
    """List all active rules in the http_request_firewall_custom phase."""
    _, rules = _get_ruleset()
    return {
        "total": len(rules),
        "budget_used": f"{len(rules)}/5",
        "rules": [
            {
                "id":          rule.get("id"),
                "description": rule.get("description"),
                "action":      rule.get("action"),
                "enabled":     rule.get("enabled", True),
                "expression":  rule.get("expression", "")[:200],
            }
            for rule in rules
        ]
    }

class RollupWithPredictions(BaseModel):
    rollup:      dict
    predictions: list[dict] | None = None

class BatchRollupPayload(BaseModel):
    items:       list[RollupWithPredictions]  # each rollup paired with its own predictions
    predictions: list[dict] | None = None     # fallback global predictions if not per-rollup

@app.post("/pipeline/rollup/batch", dependencies=[Depends(verify_secret)])
async def process_batch_rollup(payload: BatchRollupPayload):
    """
    Process multiple rollups in sequence, each with its own pred.csv rows.
    """
    results   = []
    total     = len(payload.items)
    skipped   = 0
    completed = 0
    failed    = 0

    print(f"\n── Batch of {total} rollups received")

    for i, item in enumerate(payload.items):
        rollup       = item.rollup
        # Use per-rollup predictions if provided, fall back to global
        predictions  = item.predictions or payload.predictions
        generated_at = rollup.get("generated_at", f"rollup_{i}")

        print(f"\n── [{i+1}/{total}] Processing rollup: {generated_at}")
        if predictions:
            print(f"  predictions rows: {len(predictions)}")

        try:
            maybe_reset_session()

            clusters = rollup.get("clusters", [])

            actionable = []
            for c in clusters:
                severity = _get_cluster_severity(c["cluster"])
                print(f"  Cluster {c['cluster']} severity: {severity}")
                if severity in {"CRITICAL", "HIGH", "MEDIUM"} and c["cluster"] not in handled_clusters:
                    actionable.append(c)

            if not actionable:
                print(f"  ⏭ Skipped — no new actionable clusters")
                skipped += 1
                results.append({
                    "rollup":   generated_at,
                    "status":   "skipped",
                    "reason":   "no new actionable clusters",
                    "clusters": [c["cluster"] for c in clusters],
                })
                continue

            current_WAF_rules = _fetch_current_waf_rules()
            sync_deployed_patterns()

            result = await run_pipeline(
                rollup=rollup,
                current_WAF_rules=current_WAF_rules,
                predictions=predictions,
            )

            for c in actionable:
                handled_clusters.add(c["cluster"])

            result["rollup"] = generated_at
            results.append(result)
            completed += 1

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed += 1
            results.append({
                "rollup": generated_at,
                "status": "error",
                "reason": str(e),
            })

    print(f"\n── Batch complete: {completed} completed | {skipped} skipped | {failed} failed")

    return {
        "summary": {
            "total":     total,
            "completed": completed,
            "skipped":   skipped,
            "failed":    failed,
        },
        "results": results,
    }

# ── Pipeline runner ───────────────────────────────────────────
async def run_pipeline(rollup: dict, current_WAF_rules: list, predictions: list | None = None) -> dict:
    ua_context = ""
    if predictions:
        cluster_ids = [c["cluster"] for c in rollup.get("clusters", [])]
        ua_summary  = {}
        for cid in cluster_ids:
            uas = [
                row["uas"] for row in predictions
                if row.get("cluster") == cid and row.get("uas")
            ]
            flat = []
            for ua in uas:
                try:
                    parsed = json.loads(ua.replace("'", '"')) if isinstance(ua, str) else ua
                    flat.extend(parsed if isinstance(parsed, list) else [parsed])
                except Exception:
                    flat.append(str(ua))
            ua_summary[cid] = list(set(flat))[:5]

        if ua_summary:
            ua_context = f"\nCLUSTER_USER_AGENTS:\n{json.dumps(ua_summary, indent=2)}"
    messages = [
          {
            "role": "system",
            "content": (
                "You are a cybersecurity pipeline. "
                "Do NOT explain your reasoning before calling tools. "
                "Do NOT output JSON blocks or markdown before calling tools. "
                "IMMEDIATELY call query_knowledgebase first, then proceed with other tools. "
                "Your first action must always be a tool call, never prose."
            )
        },
        {"role": "system", "content": f"CURRENT_ROLLUP:\n{json.dumps(rollup)}{ua_context}"},
        {"role": "system", "content": f"CURRENT_CLOUDFLARE_WAF_RULES:\n{json.dumps(current_WAF_rules)}"},
        {"role": "user",   "content": build_prompt(current_WAF_rules)},
    ]

    tools = [
        query_knowledgebase_tool,
        create_jira_ticket_tool,
        create_firewall_rule_tool,
    ]

    MAX_ITERS    = 5
    force_finish = False
    active_model = None
    tool_log     = []

    for i in range(MAX_ITERS):
        completion, active_model = get_completion(
            messages=messages,
            tools=tools,
            tool_choice="none" if force_finish else "auto",
        )

        msg = completion.choices[0].message
        print(f"\n── Iter {i} | model={active_model} | force_finish={force_finish} | tool_calls={bool(msg.tool_calls)}")

        if msg.tool_calls and not force_finish:
            messages.append({"role": "assistant", "tool_calls": msg.tool_calls})

            jira_called     = False
            firewall_called = False

            for call in msg.tool_calls:
                print(f"  → {call.function.name}")
                result = dispatch_tool(call)

                try:
                    parsed_result = json.loads(result) if isinstance(result, str) else result
                except json.JSONDecodeError:
                    parsed_result = result

                tool_log.append({
                    "tool":   call.function.name,
                    "args":   json.loads(call.function.arguments),
                    "result": parsed_result,
                })
                messages.append({
                    "role":         "tool",
                    "tool_call_id": call.id,
                    "content":      result,
                })
                if call.function.name == "create_jira_ticket":
                    jira_called = True
                if call.function.name == "create_consolidated_firewall_rules":
                    firewall_called = True

            if (jira_called and firewall_called) or i == MAX_ITERS - 2:
                force_finish = True

        else:
            return {
                "status":       "completed",
                "model":        active_model,
                "response":     msg.content,
                "tool_calls":   tool_log,
                "generated_at": datetime.utcnow().isoformat(),
            }

    return {"status": "max_iters_reached", "tool_calls": tool_log}

# ── Cloudflare helpers ────────────────────────────────────────
def _get_ruleset() -> tuple[str | None, list[dict]]:
    try:
        r = requests.get(CF_PHASE_URL, headers=CF_HEADERS)
        if r.status_code == 200:
            result = r.json()["result"]
            return result["id"], result.get("rules", [])
        elif r.status_code == 404:
            print("⚠ Entry point ruleset not found — creating...")
            r2 = requests.post(
                f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/rulesets",
                headers=CF_HEADERS,
                json={"kind": "zone", "name": "Custom rules", "phase": CF_PHASE, "rules": []}
            )
            r2.raise_for_status()
            return r2.json()["result"]["id"], []
        else:
            r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"✗ Could not get/create ruleset: {e}")
        return None, []

def _fetch_current_waf_rules() -> list:
    try:
        r = requests.get(CF_PHASE_URL, headers=CF_HEADERS)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("result", {}).get("rules", [])
    except Exception:
        return []

def _validate_expression(expression: str) -> tuple[bool, str]:
    if not expression.strip():
        return False, "Expression is empty."
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return False, f"Expression exceeds {MAX_EXPRESSION_LENGTH} chars ({len(expression)})."
    cf_fields = [
        "http.request.uri", "http.request.uri.path", "http.request.uri.query",
        "http.host", "ip.src", "ip.geoip.country",
        "http.user_agent", "http.request.method", "cf.threat_score"
    ]
    if not any(f in expression for f in cf_fields):
        return False, "Expression doesn't reference any known Cloudflare field."
    return True, "ok"

def _find_existing_rule(action: str, rules: list[dict]) -> dict | None:
    for rule in rules:
        if "[auto]" in rule.get("description", "").lower() and rule.get("action") == action:
            return rule
    return None

def _build_merged_expression(patterns: list[str]) -> str:
    parts = []
    for p in patterns:
        if any(f in p for f in ["http.", "ip.", "cf."]):
            parts.append(f"({p})" if not p.startswith("(") else p)
        else:
            parts.append(f'(http.request.uri.path contains "{p}")')
    return " or ".join(parts)

def delete_all_auto_rules() -> None:
    ruleset_id, rules = _get_ruleset()
    if not ruleset_id:
        print("✗ Could not get ruleset ID")
        return
    auto_rules = [r for r in rules if "[auto]" in r.get("description", "").lower()]
    if not auto_rules:
        print("No [AUTO] rules found.")
        return
    for rule in auto_rules:
        url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/rulesets/{ruleset_id}/rules/{rule['id']}"
        try:
            r = requests.delete(url, headers=CF_HEADERS)
            r.raise_for_status()
            print(f"✓ Deleted rule: {rule['id']}")
        except requests.exceptions.RequestException as e:
            print(f"✗ Failed to delete {rule['id']}: {e}")

def extract_ua_context(pred_df, cluster_ids: list) -> str:
    """Extract unique user agents for specific clusters only."""
    relevant = pred_df[pred_df["cluster"].isin(cluster_ids)]
    ua_summary = {}
    for cluster_id in cluster_ids:
        cluster_rows = relevant[relevant["cluster"] == cluster_id]
        uas = cluster_rows["uas"].dropna().tolist()
        # Flatten and deduplicate
        flat_uas = list(set([
            ua for row in uas 
            for ua in (eval(row) if isinstance(row, str) else row)
        ]))
        ua_summary[cluster_id] = flat_uas[:5]  # top 5 only
    return json.dumps(ua_summary)

# ── Jira ──────────────────────────────────────────────────────
def create_jira_ticket(summary: str, description: str, priority: str = "Medium") -> dict:
    auth    = HTTPBasicAuth(JIRA_AUTH_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     summary,
            "description": {
                "type":    "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
            },
            "issuetype": {"name": "Bug"},
            "priority":  {"name": priority},
            "labels":    ["honeypot", "automated"],
        }
    }
    try:
        response = requests.post(JIRA_REQUEST_URL, json=payload, headers=headers, auth=auth)
        response.raise_for_status()
        key = response.json().get("key")
        print(f"✓ Jira ticket created: {key}")
        return {"key": key}
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to create Jira ticket: {e}")
        return {}
    
def _build_merged_expression(patterns: list[str]) -> str:
    parts = []
    for p in patterns:
        # Strip LLM-added backslash escapes e.g. "/\.env" → "/.env"
        p = p.replace("\\.", ".")
        if any(f in p for f in ["http.", "ip.", "cf."]):
            parts.append(f"({p})" if not p.startswith("(") else p)
        else:
            parts.append(f'(http.request.uri.path contains "{p}")')
    return " or ".join(parts)

# ── Firewall ──────────────────────────────────────────────────
def create_consolidated_firewall_rules(cluster_groups: list[dict]) -> dict:
    print(f"\n── create_consolidated_firewall_rules called")
    print(f"── cluster_groups received: {json.dumps(cluster_groups, indent=2)}")

    valid_actions              = {"block", "challenge", "js_challenge", "managed_challenge"}
    ruleset_id, existing_rules = _get_ruleset()

    print(f"── ruleset_id: {ruleset_id}")
    print(f"── existing_rules count: {len(existing_rules)}")

    if not ruleset_id:
        return {"error": "Could not resolve ruleset ID"}

    manual_rules = [r for r in existing_rules if "[auto]" not in r.get("description", "").lower()]
    auto_rules   = [r for r in existing_rules if "[auto]" in r.get("description", "").lower()]
    budget_left  = RULE_BUDGET - len(manual_rules)
    results      = {}

    print(f"── manual={len(manual_rules)} | auto={len(auto_rules)} | budget_left={budget_left}")

    for group in cluster_groups:
        action      = group.get("action", "")
        cluster_ids = group.get("cluster_ids", [])
        patterns    = group.get("patterns", [])
        description = group.get("description", f"[AUTO] {action.upper()} consolidated rule")
        priority    = group.get("priority")

        print(f"\n── Group: action={action} | cluster_ids={cluster_ids} | patterns={patterns}")

        if "[auto]" not in description.lower():
            description = f"[AUTO] {description}"

        if action not in valid_actions:
            print(f"  ✗ Invalid action: {action}")
            results[action] = {"error": f"Invalid action '{action}'"}
            continue

        if not patterns:
            print(f"  ✗ No patterns provided")
            results[action] = {"error": "No patterns provided", "clusters": cluster_ids}
            continue

        # Filter already-deployed patterns
        already_deployed = deployed_patterns.get(action, set())
        new_patterns     = [p for p in patterns if p not in already_deployed]

        print(f"  already_deployed: {already_deployed}")
        print(f"  new_patterns    : {new_patterns}")

        if not new_patterns:
            print(f"  ✓ [{action.upper()}] all patterns already deployed — skipping")
            results[action] = {"status": "unchanged", "clusters": cluster_ids}
            continue

        merged = _build_merged_expression(new_patterns)
        print(f"  merged expression: {merged}")

        valid, reason = _validate_expression(merged)
        print(f"  expression valid : {valid} | reason: {reason}")

        if not valid:
            results[action] = {"error": reason, "clusters": cluster_ids}
            continue

        existing = _find_existing_rule(action, existing_rules)
        print(f"  existing [AUTO] rule: {existing.get('id') if existing else None}")

        if existing:
            rule_id       = existing["id"]
            existing_expr = existing.get("expression", "")
            updated_expr  = f"{existing_expr} or {merged}"

            print(f"  → UPDATE path | rule_id={rule_id}")
            print(f"  updated expression length: {len(updated_expr)}")

            valid, reason = _validate_expression(updated_expr)
            if not valid:
                print(f"  ✗ Updated expression invalid: {reason}")
                results[action] = {"error": f"Updated expression invalid: {reason}"}
                continue

            rules_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/rulesets/{ruleset_id}/rules/{rule_id}"
            try:
                r = requests.patch(
                    rules_url, headers=CF_HEADERS,
                    json={"expression": updated_expr, "description": description, "enabled": True, "action": action}
                )
                print(f"  PATCH status: {r.status_code}")
                print(f"  PATCH response: {r.text[:300]}")
                r.raise_for_status()
                deployed_patterns[action].update(new_patterns)
                print(f"  ✓ [{action.upper()}] rule {rule_id} UPDATED — +{len(new_patterns)} patterns ({len(updated_expr)} chars)")
                results[action] = {
                    "status":         "updated",
                    "rule_id":        rule_id,
                    "patterns_added": len(new_patterns),
                    "clusters":       cluster_ids,
                }
            except requests.exceptions.RequestException as e:
                print(f"  ✗ [{action.upper()}] update failed: {e}")
                results[action] = {"error": str(e)}

        else:
            print(f"  → CREATE path | budget_left={budget_left}")

            if budget_left <= 0:
                msg = f"Rule budget exhausted ({RULE_BUDGET}/{RULE_BUDGET})."
                print(f"  ✗ {msg}")
                results[action] = {"error": msg, "clusters": cluster_ids}
                continue

            rule_body: dict = {
                "expression":  merged,
                "action":      action,
                "description": description,
                "enabled":     True,
            }
            if priority is not None:
                rule_body["position"] = {"index": priority}

            print(f"  rule_body: {json.dumps(rule_body, indent=2)}")

            rules_url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/rulesets/{ruleset_id}/rules"
            try:
                r = requests.post(rules_url, headers=CF_HEADERS, json=rule_body)
                print(f"  POST status: {r.status_code}")
                print(f"  POST response: {r.text[:500]}")
                r.raise_for_status()
                rules    = r.json().get("result", {}).get("rules", [])
                new_rule = next((ru for ru in reversed(rules) if ru.get("expression") == merged), None)
                rule_id  = new_rule.get("id") if new_rule else "unknown"
                budget_left -= 1
                deployed_patterns[action].update(new_patterns)
                print(f"  ✓ [{action.upper()}] rule {rule_id} CREATED — {len(new_patterns)} patterns | budget left: {budget_left}")
                results[action] = {
                    "status":           "created",
                    "rule_id":          rule_id,
                    "patterns_covered": len(new_patterns),
                    "clusters":         cluster_ids,
                }
            except requests.exceptions.RequestException as e:
                print(f"  ✗ [{action.upper()}] create failed: {e}")
                print(f"  ✗ response body: {e.response.text if hasattr(e, 'response') and e.response else 'no response'}")
                results[action] = {"error": str(e)}

    print(f"\n── Results: {json.dumps(results, indent=2)}")
    return results

# ── KB query ──────────────────────────────────────────────────
def query_knowledgebase(query: str, top_k: int = 3) -> str:
    q_vec   = np.array(vo.embed([query], model="voyage-3-lite", input_type="document").embeddings)[0]
    q_vec   = q_vec / np.linalg.norm(q_vec)
    scores  = kb_vectors @ q_vec
    top_idx = np.argsort(scores)[::-1][:top_k]
    results = []
    for i in top_idx:
        if i < len(kb_entries):
            e = kb_entries[i]
            results.append(f"[KB-ID: {e['id']}] {e['title']}\nContent: {e['content']}")
    return "\n\n---\n\n".join(results)

# ── Session helpers ───────────────────────────────────────────
def maybe_reset_session():
    global handled_clusters, session_date
    today = datetime.now().date()
    if today != session_date:
        handled_clusters = set()
        session_date     = today
        sync_deployed_patterns()
        print(f"✓ Session reset for {today}")

def sync_deployed_patterns() -> None: # Sync the in-memory record of deployed patterns with Cloudflare to ensure the pipeline has an up-to-date view of what patterns have already been deployed as rules
    _, rules = _get_ruleset() # Fetch the current ruleset to get the active rules and their patterns
    for action in deployed_patterns: 
        deployed_patterns[action].clear() # Clear existing patterns for this action to resync from Cloudflare
    for rule in rules:
        if "[auto]" not in rule.get("description", "").lower(): # Only consider rules that were automatically deployed by this pipeline (identified by "[auto]" in the description) to avoid syncing manual rules
            continue
        action     = rule.get("action") # Get the action of the rule (e.g., block, challenge) to categorize the patterns accordingly
        expression = rule.get("expression", "") # Get the expression of the rule, which contains the patterns that trigger the rule, to extract and track them in the in-memory record
        if action not in deployed_patterns:
            continue 
        found = re.findall(r'contains "([^"]+)"', expression) # Extract patterns from the expression using a regex that looks for 'contains "pattern"' to identify the specific patterns that have been deployed as rules
        deployed_patterns[action].update(found)
    print(f"✓ Deployed patterns synced: { {k: len(v) for k, v in deployed_patterns.items()} }")

CLUSTER_SEVERITY = { # Mapping of cluster IDs to severity labels, used to determine which clusters are actionable for further processing in the pipeline (e.g., creating tickets, deploying rules). This mapping is based on historical data and can be updated as needed.
    -1: "CRITICAL",  0: "CRITICAL",  1: "HIGH",     2: "MEDIUM",
     3: "LOW",        4: "LOW",        5: "LOW",      6: "LOW",
     7: "CRITICAL",   8: "CRITICAL",  9: "HIGH",    10: "CRITICAL",
    11: "HIGH",      12: "CRITICAL", 13: "INFO",    14: "HIGH",
    15: "LOW",       16: "HIGH",     17: "HIGH",    18: "HIGH",
    19: "HIGH",      20: "HIGH",     21: "HIGH",
}

def _get_cluster_severity(cluster_id: int) -> str: # Helper function to get the severity label for a given cluster ID based on the predefined mapping in CLUSTER_SEVERITY. If the cluster ID is not found in the mapping, it defaults to "UNKNOWN".
    severity = CLUSTER_SEVERITY.get(cluster_id, "UNKNOWN") 
    return severity

def get_completion(messages, tools, tool_choice, models=MODELS): 
    '''
    Attempt to get a completion from the list of models in order, handling specific API errors to determine if a model is unavailable
    or lacks tool support, or if the tool use failed due to bad generation. If a model encounters an error that suggests it's unavailable or doesn't support the required features,
    the function will catch that error, log a warning, and continue to the next model in the list. If all models are exhausted without a successful completion, it raises a RuntimeError.
     ''' 
    for model in models:
        try:
            response = groq_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                stream=False
            )
            return response, model
        except APIStatusError as e:
            if e.status_code in (429, 500, 503):
                print(f"  ⚠ {model} unavailable ({e.status_code}) — trying next...")
                continue
            elif e.status_code == 400 and "tool calling" in str(e).lower():
                print(f"  ⚠ {model} no tool calling support — skipping...")
                continue
            elif e.status_code == 400 and "tool_use_failed" in str(e).lower():
                print(f"  ⚠ {model} tool use failed (bad generation) — trying next...")
                continue
            else:
                raise
        except APIConnectionError:
            continue
    raise RuntimeError("All models exhausted")

def dispatch_tool(call):
    '''
    Dispatches a tool call based on the function name specified in the call. 
    It parses the arguments from the call, determines which tool function to execute based on the function name, 
    and returns the result of that function. If the function name does not match any known tools,
    it returns an error message indicating that the tool is unknown.
    '''
    args = json.loads(call.function.arguments)
    if call.function.name == "query_knowledgebase":
        return query_knowledgebase(**args)
    elif call.function.name == "create_jira_ticket":
        args.setdefault("priority", "Medium")
        return json.dumps(create_jira_ticket(**args))
    elif call.function.name == "create_consolidated_firewall_rules":
        return json.dumps(create_consolidated_firewall_rules(**args))
    return json.dumps({"error": f"unknown tool: {call.function.name}"})

# ── Tool schemas ──────────────────────────────────────────────
query_knowledgebase_tool = {
    "type": "function",
    "function": {
        "name": "query_knowledgebase",
        "description": (
            "Semantic search over the internal cybersecurity knowledgebase. "
            "Use this to look up CVEs, MITRE ATT&CK tactics, remediation guides, "
            "cluster severity, matched patterns, and historical training fingerprints."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "e.g. 'cluster 11 severity label patterns' or 'PHP webshell CVE'"
                },
                "top_k": {"type": "integer", "default": 3}
            },
            "required": ["query"]
        }
    }
}

create_jira_ticket_tool = {
    "type": "function",
    "function": {
        "name": "create_jira_ticket",
        "description": "Create a JIRA security ticket for a detected attack cluster.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary":     {"type": "string"},
                "description": {"type": "string"},
                "priority":    {"type": "string", "enum": ["Highest", "High", "Medium", "Low"]}
            },
            "required": ["summary", "description"]
        }
    }
}

create_firewall_rule_tool = {
    "type": "function",
    "function": {
        "name": "create_consolidated_firewall_rules",
        "description": (
            "Creates or updates Cloudflare WAF rules using expression consolidation. "
            "Free tier = 5 rules max. Consolidate all clusters into max 3 action groups. "
            "Rules are OR-chained. Tool handles create vs update automatically. "
            "NEVER call once per cluster — group ALL clusters by action tier and call ONCE."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "cluster_groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["block", "challenge", "js_challenge", "managed_challenge"],
                                "description": "block=CRITICAL, managed_challenge=HIGH, challenge=MEDIUM"
                            },
                            "cluster_ids": {"type": "array", "items": {"type": "integer"}},
                            "patterns":    {"type": "array", "items": {"type": "string"}},
                            "description": {"type": "string"},
                            "priority":    {"type": "integer"}
                        },
                        "required": ["action", "cluster_ids", "patterns", "description"]
                    }
                }
            },
            "required": ["cluster_groups"]
        }
    }
}

# ── Prompt ────────────────────────────────────────────────────
def build_prompt(current_WAF_rules: list) -> str:
    return f"""
    You are a senior cybersecurity analyst writing WAF rules for Cloudflare Free tier.

    ## INPUTS
    1. CURRENT_ROLLUP — the ONLY source of truth. Contains clusters detected in the last 5 minutes.
    2. CURRENT_CLOUDFLARE_WAF_RULES — active rules already deployed.
    3. KNOWLEDGEBASE — query this for cluster severity, labels, Jira priority, matched patterns,
    and historical training fingerprints. Always query before acting on a cluster.

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

    **description** format — use EXACTLY this structure with bold headers for "WORD" inbetween *WORD* e.g, not markdown ## headers:

    **THREAT**
    <cluster_label> detected in the last 5 minutes.
    Severity: <severity> | Jira Priority: <jira_priority>

    **OBSERVED ACTIVITY**
    - Top paths: <top 3 paths from CURRENT_ROLLUP>
    - Matched patterns: <matched_patterns from CLUSTER_SEVERITY_LEVELS>
    - Request volume: <request_count> requests | 4xx ratio: <ratio_4xx>

    **WHY THIS WAS FLAGGED**
    <1-2 sentences explaining what behaviour triggered this cluster and why it is a threat>

    **RECOMMENDED WAF ACTION**
    <specific Cloudflare Free tier action — IP block / URI block / rate limit / Under Attack Mode>

    **REASONING**
    <1-2 sentences explaining why this specific WAF action was chosen over alternatives>

    **REFERENCES**
    You must call query_knowledgebase before writing this section.
    For each reference, cite the KB entry that informed your recommendation using this format:
    - [KB-ID: <id>] <title> — <1 sentence summarising the relevant finding from that entry>
    - MITRE ATT&CK T<technique_id> — <technique name> (if applicable, plain text only, no guessed URLs)

    Only include references you are certain exist. For each reference:
    - Prefer well-known stable URLs: attack.mitre.org, nvd.nist.gov, cve.mitre.org, owasp.org
    - Use this format: [Title] -> URL — one line per reference
    - If you are not confident a URL is valid and resolves, write the reference as plain text only with no URL:
    e.g. "MITRE ATT&CK T1190 — Exploit Public-Facing Application"
    - NEVER fabricate or guess URLs. A plain text reference is always better than a broken link.

    **ACTIONS TAKEN**
    The following actions were automatically executed by the pipeline:

    Jira Ticket: <this ticket — HONEY-XX>
    Cloudflare WAF Rule: <rule_id> | Action: <action> | Status: <CREATED / UPDATED / SKIPPED>
    Patterns deployed: <comma separated list of patterns added to the rule>
    Rule budget remaining: <X>/5

    **priority**: use the jira_priority value from CLUSTER_SEVERITY_LEVELS
    **Skip** clusters with severity LOW, INFO, or where jira_priority is null.

    ## FIREWALL RULES — CONSOLIDATION STRATEGY (READ CAREFULLY)
    Current rule usage: {len(current_WAF_rules)}/5 (Free tier hard limit).
    Remaining budget: {5 - len(current_WAF_rules)} rules.

    You MUST call create_consolidated_firewall_rules for any cluster with severity CRITICAL, HIGH, or MEDIUM.
    You MUST group ALL qualifying clusters into a SINGLE tool call — never call it once per cluster.

    Group clusters by action tier as follows:
    action=block             → CRITICAL severity only (severity_rank=0)
    action=managed_challenge → HIGH severity (severity_rank=1)
    action=challenge         → MEDIUM severity (severity_rank=2)

    Rules are OR-chained — one rule per action tier covers all patterns for that tier.
    The tool handles create vs update automatically:
    - If no [AUTO] rule exists for that action → creates a new rule (costs 1 budget slot)
    - If an [AUTO] rule already exists for that action → appends new patterns to it (costs 0 budget slots)

    Pattern format for the "patterns" array:
    - Pass bare path strings for path matching: "/.env", "/.git/config", "/goform/"
    - Pass full CF expressions for non-path rules: "cf.threat_score gt 50", "ip.geoip.country eq \\"CN\\""

    Example of a correct single call covering 3 clusters across 2 tiers:
    {{
    "cluster_groups": [
        {{
        "action": "block",
        "cluster_ids": [0, 12],
        "patterns": ["/.%0e/", "/cgi-bin/", "/wp-content/admin.php", "/classwithtostring.php"],
        "description": "[AUTO] CRITICAL — path traversal + PHP webshell block",
        "priority": 1
        }},
        {{
        "action": "managed_challenge",
        "cluster_ids": [18],
        "patterns": ["/.env", "/api/.env", "/.env.local", "/.env.production"],
        "description": "[AUTO] HIGH — .env secrets harvesting challenge",
        "priority": 2
        }}
    ]
    }}

    Skip clusters with severity LOW or INFO — do NOT create firewall rules for them.
    If CURRENT_ROLLUP contains only LOW/INFO clusters, do NOT call create_consolidated_firewall_rules.

    ## STRICT RULES
    - Only act on clusters present in CURRENT_ROLLUP — nothing else.
    - If a single cluster is present, output rules for that cluster only.
    - Do not invent threats not present in CURRENT_ROLLUP.
    - Do not recommend Cloudflare Pro/Business/Enterprise features.
    - Be specific: reference matched_patterns and cluster labels directly.
    - No filler, no preamble. Output the three sections only (plus Cluster 13 flag if triggered).
    - NEVER output PII in tool requests or in the response.
    - NEVER fabricate URLs. If unsure whether a URL exists, omit the link and write plain text only.
    - NEVER call create_consolidated_firewall_rules more than once per response.
    - NEVER create one cluster_group per cluster — group by action tier only.
    - NEVER escape dots in path patterns — pass "/.env" not "/\.env"
    - ALWAYS include *ACTIONS TAKEN* in every Jira ticket description, even if firewall rule failed

    ## TOOL CALL ORDER
    1. query_knowledgebase — for each cluster (severity, labels, patterns)
    2. query_knowledgebase — threat intel for HIGH/CRITICAL  
    3. create_consolidated_firewall_rules — FIRST so rule ID is known before ticket is written
    - Note the rule_id and status (created/updated/failed) from the tool response
    4. create_jira_ticket — LAST, include *ACTIONS TAKEN* using the rule_id from step 3
    You MUST call create_jira_ticket even if the firewall rule was already created.
    Include the rule_id from step 2 in the *ACTIONS TAKEN* section of the ticket.
    Do NOT stop after step 2 — Jira ticket creation is always required.

    ## ACTIONS TAKEN — MANDATORY IN EVERY JIRA TICKET
    The *ACTIONS TAKEN* section is REQUIRED in every ticket description, even if the firewall rule failed.
    Use the exact result returned by create_consolidated_firewall_rules:
    - If status=created: "Rule <rule_id> CREATED | Action: <action>"
    - If status=updated: "Rule <rule_id> UPDATED | Action: <action> | +<N> patterns added"  
    - If status=error:   "Rule creation FAILED | Reason: <error message from tool response>"
    - If status=unchanged: "Rule already covers these patterns — no changes made"

    *ACTIONS TAKEN*
    Jira Ticket: <this ticket key e.g. HONEY-33>
    Cloudflare WAF Rule: <rule_id from tool response, or "FAILED" if error>
    Action: <action tier>
    Status: <CREATED / UPDATED / FAILED / UNCHANGED>
    Patterns deployed: <list of patterns, or "none" if failed>
    Rule budget remaining: <X>/5
    Failure reason (if applicable): <error from tool response>

    ## DEBUGGING NOTE
    For evaluation purposes:
    - State which tool calls were made and for which cluster IDs
    - If a ticket was skipped, state why (severity too low, null priority, etc.)
    - If a firewall rule was skipped, state why (LOW/INFO severity, budget exhausted, etc.)
    - State the resulting Jira ticket ID and Cloudflare rule ID for each action taken
    """

# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("LLM_pipeline:app", host="0.0.0.0", port=8000, reload=False)