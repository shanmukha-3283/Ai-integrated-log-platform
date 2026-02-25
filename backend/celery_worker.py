import os
import json
from celery import Celery
from pymongo import MongoClient
# Use direct imports (not 'backend.parser') because this file IS inside the backend dir
from parser import LogParser
from anomaly import AnomalyDetector
try:
    from ai_analysis import AIAnalyzer
except Exception:
    AIAnalyzer = None

# ─────────────────────────────────────────────────────────────
# Celery app — uses Redis as broker AND result backend
# ─────────────────────────────────────────────────────────────
celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND",
                      os.getenv("REDIS_URL", "redis://localhost:6379/0")),
)

# ─────────────────────────────────────────────────────────────
# MongoDB — use MONGODB_URL or MONGO_URI (both are checked)
# ─────────────────────────────────────────────────────────────
_mongo_uri = os.getenv("MONGODB_URL", os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
client = MongoClient(_mongo_uri)
db = client["log_platform"]


@celery_app.task(name="process_log_file")
def process_log_file(job_id: str, content: str, filename: str):
    """
    Background task: parse → detect anomalies → store results in MongoDB.
    This runs inside the Celery worker container, NOT in the web server.
    """
    try:
        # ── 1. Parse log lines ──────────────────────────────────
        parser = LogParser()
        # content is a str (decoded by the API before handing to Celery)
        parsed_logs = parser.parse_file(content)

        # ── 2. Detect anomalies ───────────────────────────────
        # AnomalyDetector.compute_anomaly_score() adds 'anomaly_score' to each log
        detector = AnomalyDetector()
        try:
            scored_logs = detector.compute_anomaly_score(parsed_logs)
        except Exception:
            # If scoring fails, still store the parsed logs without scores
            scored_logs = parsed_logs

        # ── 3. Store each log entry in MongoDB ────────────────
        if scored_logs:
            db.logs.insert_many(scored_logs)

        # ── 4. Mark job completed ─────────────────────────────
        db.jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "processed_count": len(scored_logs),
                    "filename": filename,
                }
            },
        )

    except Exception as e:
        # Mark job failed so the API can report what went wrong
        db.jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e),
                }
            },
        )
        # Re-raise so Celery marks the task as FAILURE (visible in Flower)
        raise
