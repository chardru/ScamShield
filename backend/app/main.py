"""
ScamShield Backend - Main FastAPI Application.

Real-Time Scam Conversation Detector.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.database import init_db
from app.routers import health, analysis, transcription, reports, notifications, websocket

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ScamShield API",
    description="Real-Time Scam Conversation Detector — Backend API",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(transcription.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(websocket.router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info("🛡️ ScamShield Backend starting...")
    init_db()
    logger.info(f"Gemini: {'✅ configured' if settings.has_gemini_key else '❌ not configured (demo mode)'}")
    logger.info(f"Sarvam: {'✅ configured' if settings.has_sarvam_key else '❌ not configured (demo mode)'}")
    logger.info(f"Telegram: {'✅ configured' if settings.has_telegram_config else '❌ not configured'}")
    logger.info("🛡️ ScamShield Backend ready!")
