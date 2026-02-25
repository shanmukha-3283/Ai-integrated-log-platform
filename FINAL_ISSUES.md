# Top 5 Issues Beginners Hit at the End of the Project

---

## Issue 1 — "Connection refused" when running `e2e_test.py`

**Symptom:**
```
❌ Backend not reachable at http://localhost:8000
Error: HTTPConnectionPool ... Connection refused
```

**Why this happens:**  
The backend server isn't running, or it started with an error and crashed silently.

**Exact fix — verify first:**
```bash
python -c "import requests; print(requests.get('http://localhost:8000/health').json())"
```

**Then start the backend:**
```bash
# If using Docker (recommended):
docker compose up

# If running locally:
cd backend
source venv/bin/activate          # or .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Also check:** Celery worker and Redis must both be running too.  
`docker compose ps` will show you which containers are up/down.

---

## Issue 2 — SSE streaming doesn't work in the browser

**Symptom:**  
The AI answer never appears. Network tab shows the request is pending forever  
or the browser shows a CORS or type error.

**Why this happens:**  
Either the `Content-Type` is wrong, CORS is blocking the stream, or the  
frontend `EventSource` is reading from the wrong URL.

**Exact fix:**

1. Confirm the endpoint returns the right content type (in `main.py`):
   ```python
   return StreamingResponse(event_stream(), media_type="text/event-stream")
   ```

2. In the browser DevTools → Network tab, click the `/ask-ai` request and  
   confirm the **Response Headers** show:
   ```
   Content-Type: text/event-stream
   ```

3. If you're on `http://localhost:5173` and the backend is `http://localhost:8000`,  
   Chrome will block SSE from a mixed origin. Fix: add the Vite proxy in `vite.config.js`:
   ```js
   server: {
     proxy: {
       "/ask-ai": "http://localhost:8000",
     }
   }
   ```
   Then call `/ask-ai` (no hostname) from the frontend.

---

## Issue 3 — "FAISS index is empty after restart"

**Symptom:**  
After `docker compose restart` or `docker compose up`, vector similarity search  
returns no results even though logs are in MongoDB.

**Why this happens:**  
FAISS is an **in-memory** index. When the process restarts, the index is gone.  
It isn't persisted to disk automatically.

**Exact fix — rebuild index on startup in `main.py`:**
```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: rebuild FAISS from all embeddings stored in MongoDB
    print("🔄 Rebuilding FAISS index from MongoDB...")
    docs = list(logs_collection.find({"embedding": {"$exists": True}}))
    if docs:
        import numpy as np
        vectors = np.array([d["embedding"] for d in docs], dtype="float32")
        faiss_index.add(vectors)
        print(f"   ✅ Loaded {len(docs)} embeddings into FAISS")
    yield
    # On shutdown: (nothing needed for FAISS)

app = FastAPI(title="AI Log Platform", lifespan=lifespan)
```

For a permanent fix, use `faiss.write_index(index, "index.faiss")` on write  
and `faiss.read_index("index.faiss")` on startup.

---

## Issue 4 — "Celery task says SUCCESS but logs not in MongoDB"

**Symptom:**  
`flower` (or Celery logs) shows `Task succeeded`, the job status shows  
`completed`, but `GET /logs` returns 0 results.

**Why this happens:**  
The Celery worker container is connecting to `localhost:27017`, but inside  
Docker, `localhost` is the **worker's own container** — which has no MongoDB.  
It needs to use the service name `mongodb`.

**Exact fix — check environment variables:**
```bash
docker compose exec celery-worker env | grep MONGO
# Should show: MONGO_URI=mongodb://mongodb:27017/
# NOT:         MONGO_URI=mongodb://localhost:27017/
```

Fix in `docker-compose.yml` under the `celery-worker` service:
```yaml
celery-worker:
  environment:
    - MONGO_URI=mongodb://mongodb:27017/
    - REDIS_URL=redis://redis:6379/0
```

The exact service names (`mongodb`, `redis`) must match what you named  
the services in `docker-compose.yml`.

---

## Issue 5 — "CORS error in browser console"

**Symptom:**
```
Access to fetch at 'http://localhost:8000/logs' from origin 'http://localhost:5173'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header.
```

**Why this happens:**  
The CORS middleware is either missing, misconfigured, or added **after** the  
routes are registered (FastAPI applies middleware in reverse order).

**Exact fix — in `main.py`, CORS must be the FIRST middleware, before routes:**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Log Platform")

# ✅ Add CORS FIRST — before any @app.get / @app.post
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Create React App
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes come AFTER middleware
@app.get("/health")
async def health(): ...
```

> **Quick test:** Open DevTools → Network → click any failing request →  
> look at **Response Headers**. You should see  
> `Access-Control-Allow-Origin: http://localhost:5173`
