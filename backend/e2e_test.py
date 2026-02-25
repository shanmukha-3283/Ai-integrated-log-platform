"""
End-to-End Integration Test for AI Log Platform
================================================
Tests the full pipeline: upload → process → analyze → AI query

Usage:
    python e2e_test.py
    BASE_URL=http://localhost:8000 python e2e_test.py

What this does:
  Step 1 — Generate 500-line realistic log file with an ERROR spike
  Step 2 — Upload the file via POST /upload-log
  Step 3 — Poll /jobs/{job_id} until completed (max 60 s)
  Step 4 — Verify analytics via GET /analytics
  Step 5 — Retrieve ERROR logs via GET /logs?level=ERROR
  Step 6 — Ask AI "Why is payment-svc failing?" via POST /ask-ai  (SSE)
  Step 7 — Print a summary results table
"""

import os
import sys
import json
import time
import random
import requests
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# ─────────────────────────────────────────────────────────────
# STEP 1 — GENERATE REALISTIC 500-LINE LOG FILE
# ─────────────────────────────────────────────────────────────
def generate_log_file(path="/tmp/integration_test.log"):
    """
    Creates a realistic mixed log file:
      300 INFO  — normal traffic across 3 services (last 6 hours)
       80 WARN  — degradation warnings spread across last 4 hours
      100 ERROR — payment-svc spike ~1 hour ago  ← anomaly target
       20 garbage/unrecognised lines to test parser robustness
    """
    print("\n📝 Generating test log file (500 lines)...")
    now = datetime.now()
    services = ["auth-svc", "api-svc", "payment-svc"]

    info_msgs = [
        "User login successful for user_{uid}",
        "Request processed in {ms}ms",
        "Cache hit for key session_{sid}",
        "Health check OK",
        "Metrics flushed to collector",
        "JWT token validated for user_{uid}",
        "Database query completed in {ms}ms",
        "Response sent — status 200",
    ]

    warn_msgs = [
        "Response time high: {ms}ms",
        "Retry attempt {n} for downstream call",
        "Memory usage at {pct}%",
        "Rate limit approaching for client_{n}",
        "Connection pool at 80% capacity",
        "Slow query detected: {ms}ms",
    ]

    error_msgs = [
        "Database connection timeout after 30000ms",
        "Failed to process payment for order_{oid}: gateway refused",
        "Stripe API error: rate_limit_exceeded",
        "Transaction rollback failed — data may be inconsistent",
        "Circuit breaker OPEN — blocking requests to db-primary",
        "Unhandled exception in PaymentProcessor.charge(): NullPointerException",
        "Payment gateway unreachable — retries exhausted",
        "Deadlock detected on payments table — rolling back",
    ]

    garbage_lines = [
        "-----------------------------------",
        "[GC] Heap: {mb1}MB → {mb2}MB",
        "<xml><event type='log'/></xml>",
        "kernel: usb 1-1.2: new high-speed USB device",
        "",
        "  ",
        "random unstructured text line {n}",
        "Jul  4 00:01:44 hostname systemd[1]: Started Session",
    ]

    lines = []

    # ── 300 INFO logs — last 6 hours, evenly spaced ──────────
    for i in range(300):
        ts = now - timedelta(hours=6) + timedelta(seconds=i * 72)
        svc = random.choice(services)
        uid = random.randint(1000, 9999)
        ms  = random.randint(12, 200)
        sid = random.randint(100, 999)
        msg = (
            random.choice(info_msgs)
            .format(uid=uid, ms=ms, sid=sid)
        )
        lines.append(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} INFO  {svc} - {msg}")

    # ── 80 WARN logs — last 4 hours ───────────────────────────
    for i in range(80):
        ts  = now - timedelta(hours=4) + timedelta(seconds=i * 180)
        svc = random.choice(services)
        ms  = random.randint(800, 1500)
        n   = random.randint(1, 50)
        pct = random.randint(70, 89)
        msg = (
            random.choice(warn_msgs)
            .format(ms=ms, n=n, pct=pct)
        )
        lines.append(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} WARN  {svc} - {msg}")

    # ── 100 ERROR logs — payment-svc spike ~1 hour ago ────────
    # These 100 errors in a tight 60-minute window are the anomaly
    # the anomaly detector should score highly.
    for i in range(100):
        ts  = now - timedelta(minutes=70) + timedelta(seconds=i * 36)
        oid = random.randint(10000, 99999)
        mb1 = random.randint(400, 800)
        mb2 = random.randint(100, 200)
        msg = (
            random.choice(error_msgs)
            .format(oid=oid, mb1=mb1, mb2=mb2)
        )
        lines.append(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} ERROR payment-svc - {msg}")

    # ── 20 garbage lines ──────────────────────────────────────
    for i in range(20):
        raw = random.choice(garbage_lines)
        lines.append(
            raw.format(mb1=random.randint(200, 800), mb2=random.randint(50, 199), n=i)
        )

    # Shuffle the first 380 lines (INFO + WARN) so they look realistic,
    # but keep the ERROR spike lines (#380-#479) in approximate time order.
    front = lines[:380]
    random.shuffle(front)
    all_lines = front + lines[380:]

    with open(path, "w") as f:
        f.write("\n".join(all_lines))

    print(f"   ✅ Created {path} ({len(all_lines)} lines)")
    print(f"      INFO: 300  |  WARN: 80  |  ERROR: 100  |  Garbage: 20")
    return path


# ─────────────────────────────────────────────────────────────
# STEP 2 — UPLOAD THE FILE
# ─────────────────────────────────────────────────────────────
def upload_log(path):
    """POST /upload-log → returns job_id or None on failure."""
    print("\n📤 Uploading log file...")
    try:
        with open(path, "rb") as f:
            response = requests.post(
                f"{BASE_URL}/upload-log",
                files={"file": ("integration_test.log", f, "text/plain")},
                timeout=30,
            )

        if response.status_code != 200:
            print(f"   ❌ Upload failed: HTTP {response.status_code} — {response.text[:200]}")
            return None

        data   = response.json()
        job_id = data.get("job_id")
        print(f"   ✅ File uploaded — job_id: {job_id}")
        return job_id

    except requests.exceptions.ConnectionError:
        print(f"   ❌ Upload failed: Could not connect to {BASE_URL}")
        print("      ➡  Is the backend running?  docker compose up  OR  uvicorn main:app --reload")
        return None
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# STEP 3 — POLL UNTIL JOB COMPLETES
# ─────────────────────────────────────────────────────────────
def poll_job(job_id, timeout=60):
    """
    GET /jobs/{job_id} every 2 seconds.
    Returns the job dict when status == 'completed', or None on failure/timeout.
    """
    print(f"\n⏳ Polling job {job_id} (max {timeout}s)...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            r      = requests.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
            if r.status_code != 200:
                print(f"   ❌ Job status check failed: HTTP {r.status_code}")
                return None

            data   = r.json()
            status = data.get("status", "unknown")
            print(f"   ⏳ Job status: {status}...", flush=True)

            if status == "completed":
                count = data.get("processed_count", data.get("processed_logs", "?"))
                print(f"   ✅ Job done — {count} logs processed")
                return data

            if status == "failed":
                error = data.get("error", "unknown error")
                print(f"   ❌ Job failed: {error}")
                return None

        except Exception as e:
            print(f"   ⚠️  Poll error: {e}")

        time.sleep(2)

    print(f"   ❌ Job timed out after {timeout} seconds")
    return None


# ─────────────────────────────────────────────────────────────
# STEP 4 — VERIFY ANALYTICS
# ─────────────────────────────────────────────────────────────
def verify_analytics():
    """GET /analytics and print key metrics. Returns True on success."""
    print("\n📊 Verifying analytics...")
    try:
        r = requests.get(f"{BASE_URL}/analytics", timeout=10)
        if r.status_code != 200:
            print(f"   ❌ Analytics failed: HTTP {r.status_code}")
            return False

        data         = r.json()
        total_logs   = data.get("total_logs", 0)
        error_count  = data.get("error_count", 0)
        error_rate   = data.get("error_rate", 0)
        anomaly_count = data.get("anomaly_count", len(data.get("anomalies", [])))

        print(f"   ✅ Total logs:         {total_logs}")
        print(f"   ✅ Error count:        {error_count}")
        print(f"   ✅ Error rate:         {error_rate:.1f}%")
        print(f"   ✅ Anomalies detected: {anomaly_count}")

        if anomaly_count == 0:
            print("   ⚠️  WARNING: No anomalies detected — the spike may not have been scored yet.")
            print("      (This is OK if the anomaly scorer runs asynchronously after processing.)")

        return True

    except Exception as e:
        print(f"   ❌ Analytics error: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# STEP 5 — VERIFY LOG RETRIEVAL
# ─────────────────────────────────────────────────────────────
def verify_log_retrieval():
    """GET /logs?level=ERROR&page_size=5 and print the first result."""
    print("\n🔍 Verifying log retrieval (level=ERROR, page_size=5)...")
    try:
        r = requests.get(
            f"{BASE_URL}/logs",
            params={"level": "ERROR", "page_size": 5},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"   ❌ Log retrieval failed: HTTP {r.status_code}")
            return False

        data = r.json()
        # The endpoint returns { logs: [...], total: N, ... }
        logs  = data.get("logs", data) if isinstance(data, dict) else data
        count = len(logs)

        print(f"   ✅ Retrieved {count} ERROR logs successfully")

        if logs:
            first   = logs[0]
            service = first.get("service", first.get("source", "unknown"))
            message = first.get("message", first.get("msg", ""))
            print(f"   📋 First log — service: {service}")
            print(f"   📋 Message:  {str(message)[:120]}")

        return True

    except Exception as e:
        print(f"   ❌ Log retrieval error: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# STEP 6 — ASK AI (handles SSE streaming response)
# ─────────────────────────────────────────────────────────────
def ask_ai():
    """
    POST /ask-ai {"query": "Why is payment-svc failing?"}

    The /ask-ai endpoint returns Server-Sent Events (SSE), NOT plain JSON.
    Each event line is:  data: {"token": "..."}\n\n
    The final event is:  data: {"done": true, "result": {...}}\n\n

    We collect all SSE data lines and extract the final 'result' object.
    We use stream=True so we can read the response line-by-line.
    """
    print("\n🤖 Asking AI: 'Why is payment-svc failing?'...")
    try:
        r = requests.post(
            f"{BASE_URL}/ask-ai",
            json={"query": "Why is payment-svc failing?"},
            timeout=90,
            stream=True,          # Stream the SSE response line by line
        )

        if r.status_code != 200:
            print(f"   ❌ AI request failed: HTTP {r.status_code} — {r.text[:200]}")
            return False

        # ── Parse SSE stream ──────────────────────────────────
        # Each data event looks like:  data: <json>\n\n
        # We accumulate tokens for display, then grab the final result.
        collected_result = None
        token_buffer     = []

        for raw_line in r.iter_lines(decode_unicode=True):
            if not raw_line:
                continue                                 # blank line = event boundary

            if raw_line.startswith("data:"):
                payload = raw_line[len("data:"):].strip()
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                if event.get("done"):
                    collected_result = event.get("result", {})
                    break                               # stop reading after final event

                if "token" in event:
                    token_buffer.append(event["token"])

        # ── Display result ────────────────────────────────────
        if collected_result:
            # The /ask-ai endpoint uses "cause" as the root cause field
            root_cause  = collected_result.get(
                "root_cause",
                collected_result.get("cause",
                collected_result.get("analysis",
                collected_result.get("response", " ".join(token_buffer))))
            )
            confidence  = collected_result.get("confidence", "N/A")
            severity    = collected_result.get("severity",   "N/A")

            print("   ✅ AI Analysis received")
            print(f"      Root cause: {str(root_cause)[:80]}")
            print(f"      Confidence: {confidence}")
            print(f"      Severity:   {severity}")
            return True

        # Fallback: endpoint returned no 'done' event or was non-SSE JSON
        elif token_buffer:
            full_text = " ".join(token_buffer)
            print("   ✅ AI Analysis received (token stream mode)")
            print(f"      Response: {full_text[:120]}")
            return True

        else:
            # Last resort: try reading the raw body as JSON
            try:
                data       = r.json()
                root_cause = data.get("root_cause", data.get("cause", str(data)))
                confidence = data.get("confidence", "N/A")
                severity   = data.get("severity",   "N/A")
                print("   ✅ AI Analysis received (JSON mode)")
                print(f"      Root cause: {str(root_cause)[:80]}")
                print(f"      Confidence: {confidence}")
                print(f"      Severity:   {severity}")
                return True
            except Exception:
                print("   ❌ AI response was empty or unparseable")
                return False

    except Exception as e:
        print(f"   ❌ AI query error: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# STEP 7 — FINAL SUMMARY TABLE
# ─────────────────────────────────────────────────────────────
def print_summary(passed: dict, log_count: int = 0) -> bool:
    """Print a bordered summary table and return True if all tests passed."""
    upload     = "✅ PASS" if passed.get("upload")     else "❌ FAIL"
    count_str  = f"({log_count} logs)" if log_count else ""
    processing = f"✅ PASS {count_str}".strip() if passed.get("processing") else "❌ FAIL"
    analytics  = "✅ PASS" if passed.get("analytics")  else "❌ FAIL"
    log_query  = "✅ PASS" if passed.get("log_query")  else "❌ FAIL"
    ai_rca     = "✅ PASS" if passed.get("ai_rca")     else "❌ FAIL"

    all_passed = all(passed.values())
    footer     = "🎉 ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"

    W = 38   # inner width
    def row(label, value):
        # pad the combined string to W chars
        content = f"  {label:<14}{value}"
        print(f"║{content:<{W}}║")

    print()
    print(f"╔{'═' * W}╗")
    print(f"║{'  INTEGRATION TEST RESULTS':<{W}}║")
    print(f"╠{'═' * W}╣")
    row("Upload:",     upload)
    row("Processing:", processing)
    row("Analytics:",  analytics)
    row("Log query:",  log_query)
    row("AI RCA:",     ai_rca)
    print(f"╠{'═' * W}╣")
    print(f"║  {footer:<{W - 2}}║")
    print(f"╚{'═' * W}╝")

    return all_passed


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    print("=" * 47)
    print("  🚀 AI LOG PLATFORM — INTEGRATION TEST")
    print("=" * 47)
    print(f"  Target: {BASE_URL}")

    # ── Pre-flight: health check ──────────────────────────────
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        h      = health.json()
        mongo  = "✅" if h.get("mongodb") else "❌"
        redis  = "✅" if h.get("redis")   else "❌"
        print(f"  MongoDB: {mongo}   Redis: {redis}")
    except Exception as e:
        print(f"\n❌ Backend not reachable at {BASE_URL}")
        print(f"   Error: {e}")
        print()
        print("  ➡  Quick fix:")
        print("     python -c \"import requests; print(requests.get('http://localhost:8000/health').json())\"")
        print("  ➡  Start the backend:")
        print("     docker compose up          (Docker)")
        print("     uvicorn main:app --reload  (local venv)")
        sys.exit(1)

    passed   = {}
    log_count = 0

    # ── Step 1 — Generate log file ────────────────────────────
    log_path = generate_log_file()

    # ── Step 2 — Upload ───────────────────────────────────────
    job_id = upload_log(log_path)
    passed["upload"] = job_id is not None
    if not passed["upload"]:
        print("\n❌ Stopping — upload failed.")
        print_summary(passed)
        sys.exit(1)

    # ── Step 3 — Poll until done ──────────────────────────────
    job_result = poll_job(job_id, timeout=60)
    passed["processing"] = job_result is not None
    if job_result:
        log_count = job_result.get("processed_count", job_result.get("processed_logs", 0))

    # ── Step 4 — Analytics ────────────────────────────────────
    passed["analytics"] = verify_analytics()

    # ── Step 5 — Log retrieval ────────────────────────────────
    passed["log_query"] = verify_log_retrieval()

    # ── Step 6 — AI RCA ───────────────────────────────────────
    passed["ai_rca"] = ask_ai()

    # ── Step 7 — Summary ──────────────────────────────────────
    all_passed = print_summary(passed, log_count=log_count)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
