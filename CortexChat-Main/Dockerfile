# ─────────────────────────────────────────────────────────────────────────────
# CortexChat — Backend Dockerfile
# Build:   docker build -t CortexChat-backend .
# Run:     docker run -p 8000:8000 --env-file .env CortexChat-backend
# ─────────────────────────────────────────────────────────────────────────────

# Use slim Python 3.12 — matching our project spec
FROM python:3.12-slim

# ─── System dependencies ─────────────────────────────────────────────────────
# tesseract-ocr: for image OCR (pytesseract)
# libgl1:        required by PyMuPDF (PDF parsing)
# libglib2.0-0:  dependency of libgl1
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Install Python dependencies ─────────────────────────────────────────────
# Copy requirements first so Docker can cache this layer
# (only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ─── Copy application code ────────────────────────────────────────────────────
COPY backend/ ./backend/
COPY .env .env

# ─── Storage directories ──────────────────────────────────────────────────────
# Mount volumes here in production to persist user files, DB, and FAISS indexes
RUN mkdir -p uploads data

# ─── Expose port ─────────────────────────────────────────────────────────────
EXPOSE 8000

# ─── Start server ────────────────────────────────────────────────────────────
# 2 workers for free-tier hosts (512 MB RAM); increase for paid tiers
CMD ["gunicorn", "backend.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
