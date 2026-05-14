"""
backend/main.py — FastAPI Application Entry Point.

This is the main orchestration module for the CortexChat backend.
It constructs the FastAPI app instance, configures middleware,
registers routers, and serves the frontend.

Run:
    uvicorn backend.main:app --reload --port 8000
"""

import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import init_db
from backend.routers import auth, chat, upload, export, user
from backend.services.cleanup_service import auto_delete_old_documents

# ─────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────
settings = get_settings()


# ─────────────────────────────────────────────────────────────
# App Lifespan
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle handler.
    """

    # Initialize database
    await init_db()

    # Ensure uploads directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Start cleanup background task
    asyncio.create_task(auto_delete_old_documents())

    print("✅ CortexChat API started successfully.")

    yield

    print("🛑 CortexChat API shutting down.")


# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="CortexChat API",
    description="AI-powered document chat and summarization platform.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────
# CORS Middleware
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# API Routers
# All backend routes use /api prefix
# ─────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(user.router, prefix="/api")


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0"
    }


# ─────────────────────────────────────────────────────────────
# Root Redirect
# ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/pages/index.html")


# ─────────────────────────────────────────────────────────────
# Serve Frontend Static Files
# ─────────────────────────────────────────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"

if frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="frontend"
    )
    print(f"✅ Frontend mounted from: {frontend_dir}")
else:
    print(f"⚠️ Frontend directory not found: {frontend_dir}")
