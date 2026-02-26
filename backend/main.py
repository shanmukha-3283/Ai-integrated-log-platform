from fastapi import FastAPI, UploadFile, File, Path, Query, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
import os
import json
import asyncio
from dotenv import load_dotenv
from datetime import datetime, timedelta
from bson import ObjectId
from typing import List, Optional, Dict, Any
from ai_analysis import AIAnalyzer
from database import db, init_db

load_dotenv()

# Initialize AI Analyzer
ai_analyzer = AIAnalyzer()

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict (ObjectId → str)."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out

app = FastAPI(title="AI Log Platform")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://shanmukha-3283.github.io"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Run core startup tasks"""
    await init_db()

# Reference collections through the shared database instance
jobs_collection = db.db["jobs"]
logs_collection = db.db["logs"]

@app.get("/health")
async def health_check():
    """Check if services are running"""
    try:
        # Test MongoDB connection via the shared client
        await db.client.admin.command("ping")
        mongo_ok = True
    except Exception as e:
        print(f"Health check error: {e}")
        mongo_ok = False
    
    try:
        # Test Redis connection — read from env, not hardcoded localhost
        import redis as redis_lib
        _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis_lib.from_url(_redis_url, socket_connect_timeout=2)
        redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    
    return {
        "status": "ok",
        "mongodb": mongo_ok,
        "redis": redis_ok
    }

@app.post("/upload-log")
async def upload_log(file: UploadFile = File(...)):
    """Waiter takes the bag of logs, gives customer a ticket number, passes bag to kitchen (Celery)"""
    # Validate file
    if not file.filename.endswith((".log", ".txt")):
        raise HTTPException(status_code=400, detail="File must be .log or .txt")
    
    if file.size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="File size exceeds 10MB")
    
    # Create job
    job_id = f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    job_data = {
        "job_id": job_id,
        "filename": file.filename,
        "status": "queued",
        "created_at": datetime.now()
    }
    
    # Store job in MongoDB
    jobs_collection.insert_one(job_data)
    
    # Process file in background
    content = await file.read()
    # NOTE: Celery .delay() is synchronous — do NOT await it
    from celery_worker import process_log_file
    process_log_file.delay(job_id, content.decode("utf-8", errors="replace"), file.filename)
    
    return {
        "job_id": job_id,
        "filename": file.filename,
        "status": "queued",
        "created_at": job_data["created_at"].isoformat()
    }

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str = Path(...)):
    """Customer checks their ticket status"""
    job = await jobs_collection.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job["job_id"],
        "filename": job["filename"],
        "status": job["status"],
        "created_at": job["created_at"].isoformat(),
        "processed_count": job.get("processed_count", 0),
        "anomalies": job.get("anomalies", []),
        "error": job.get("error")
    }

@app.get("/logs")
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    service: Optional[str] = None,
    level: Optional[str] = None,
    min_anomaly_score: Optional[float] = None,
    search: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """Query logs with filters and pagination"""
    filter_query = {}
    
    # Add service filter
    if service:
        filter_query["service"] = service
    
    # Add level filter
    if level:
        filter_query["level"] = level
    
    # Add anomaly score filter
    if min_anomaly_score is not None:
        filter_query["anomaly_score"] = {"$gte": min_anomaly_score}
    
    # Add search filter
    if search:
        filter_query["$text"] = {"$search": search}
    
    # Add time range filter
    if start_time:
        filter_query["timestamp"] = {"$gte": datetime.fromisoformat(start_time)}
    if end_time:
        filter_query["timestamp"] = {"$lte": datetime.fromisoformat(end_time)}
    
    # Pagination
    skip = (page - 1) * page_size
    limit = page_size
    
    # Get total count
    total = await logs_collection.count_documents(filter_query)
    
    # Get paginated results
    cursor = logs_collection.find(filter_query).skip(skip).limit(limit).sort("timestamp", -1)
    results = await cursor.to_list(length=limit)
    
    return {
        "logs": [serialize_doc(doc) for doc in results],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size
    }

@app.get("/analytics")
async def get_analytics():
    """Generate analytics about log data"""
    # Total logs (last 24 hours)
    total_logs = await logs_collection.count_documents({
        "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
    })
    
    # Error count (level: ERROR)
    error_count = await logs_collection.count_documents({
        "level": "ERROR",
        "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
    })
    
    # Error rate
    error_rate = round(error_count / total_logs * 100, 2) if total_logs > 0 else 0
    
    # Top 5 services by log count
    top_services_cursor = logs_collection.aggregate([
        {"$match": {"timestamp": {"$gte": datetime.now() - timedelta(days=1)}}},
        {"$group": {"_id": "$service", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ])
    top_services = await top_services_cursor.to_list(length=5)
    
    # Anomalies (score >= 0.7)
    anomaly_count = await logs_collection.count_documents({
        "anomaly_score": {"$gte": 0.7},
        "timestamp": {"$gte": datetime.now() - timedelta(days=1)}
    })
    
    # Hourly breakdown (last 12 hours)
    hourly_breakdown_cursor = logs_collection.aggregate([
        {"$match": {"timestamp": {"$gte": datetime.now() - timedelta(hours=12)}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%H", "date": "$timestamp"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ])
    hourly_breakdown = await hourly_breakdown_cursor.to_list(length=12)
    
    return {
        "total_logs": total_logs,
        "error_count": error_count,
        "error_rate": error_rate,
        "top_services": [{"service": service["_id"], "count": service["count"]} for service in top_services],
        "anomaly_count": anomaly_count,
        "hourly_breakdown": [{"hour": hour["_id"], "count": hour["count"]} for hour in hourly_breakdown]
    }

@app.post("/analyze")
async def analyze_logs():
    """AI analysis of log data"""
    # This would typically involve more complex analysis
    return {
        "message": "AI analysis endpoint",
        "suggestion": "Consider implementing machine learning models for pattern detection"
    }


class AskAIRequest(BaseModel):
    query: str
    log_ids: List[str] = []
    model: str = "gpt-4o"


@app.post("/ask-ai")
async def ask_ai(request: AskAIRequest):
    """AI-powered log analysis with SSE streaming response"""
    query = request.query
    log_ids = request.log_ids
    model_choice = request.model

    async def event_stream():
        try:
            # Fetch relevant logs for context
            filter_query = {}
            if log_ids:
                filter_query["_id"] = {"$in": [ObjectId(lid) for lid in log_ids]}

            cursor = logs_collection.find(filter_query).sort("timestamp", -1).limit(50)
            recent_logs = await cursor.to_list(length=50)

            # Build initial context
            error_logs = [l for l in recent_logs if l.get("level") == "ERROR"]
            warn_logs = [l for l in recent_logs if l.get("level") == "WARN"]
            services = list(set(l.get("service", "unknown") for l in recent_logs))
            anomalies = [l for l in recent_logs if (l.get("anomaly_score", 0) or 0) >= 0.7]

            # Initial summary for streaming
            response_text = f"Neural Link established. Routing inquiry to {model_choice}...\n"
            response_text += f"Analyzing {len(recent_logs)} transmission logs across {len(services)} services.\n"
            
            words = response_text.split(" ")
            for word in words:
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.04)

            # --- REAL AI ANALYSIS ---
            try:
                log_texts = [f"[{l.get('level')}] {l.get('service')}: {l.get('message')}" for l in recent_logs[:15]]
                analysis = await ai_analyzer.analyze_root_cause(log_texts, model=model_choice)
                
                result = {
                    "cause": analysis.get("cause", "Analysis inconclusive"),
                    "confidence": analysis.get("confidence", "MEDIUM"),
                    "severity": analysis.get("severity", "MEDIUM"),
                    "affected_services": analysis.get("affected_services", services[:3]),
                    "recommendation": analysis.get("recommendation", "Review system health monitors."),
                    "impact": analysis.get("impact", "Service degradation likely."),
                    "solution": analysis.get("solution", "Manual inspection required.")
                }
            except Exception as ai_err:
                print(f"AI error: {ai_err}")
                result = {
                    "cause": "AI subsystem busy or unavailable.",
                    "confidence": "LOW",
                    "severity": "HIGH",
                    "recommendation": "Try a different model or check API quota.",
                    "solution": "Check backend .env for valid OPENAI_API_KEY."
                }

            yield f"data: {json.dumps({'done': True, 'result': result})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'done': True, 'result': {'error': str(e)}})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/stream")
async def stream_logs():
    """Stream logs in real-time"""
    async def event_stream():
        async for doc in logs_collection.find().sort("timestamp", -1).limit(10):
            yield f"data: {json.dumps(serialize_doc(doc))}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
