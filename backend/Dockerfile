FROM docker.io/library/python:3.11-slim
# ↑ Start from an official Python 3.11 image.
#   'slim' means minimal size — no extra tools included.

WORKDIR /app
# ↑ All future commands run from /app inside the container.
#   Like doing 'cd /app' permanently.

COPY requirements.txt .
# ↑ Copy requirements BEFORE copying code.
#   Docker caches each step. If code changes but 
#   requirements don't, it won't re-install packages.
#   This makes rebuilds much faster.

RUN pip install --no-cache-dir -r requirements.txt
# ↑ Install all dependencies.
#   --no-cache-dir keeps the image size smaller.

COPY . .
# ↑ Now copy all our code into the container.

EXPOSE 8000
# ↑ Document that this container uses port 8000.
#   (Doesn't actually open the port — docker run does that.)

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
# ↑ Command to run when container starts.
#   --host 0.0.0.0 is required in Docker so other 
#   containers can reach it (not just localhost).
