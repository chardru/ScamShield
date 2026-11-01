"""
ScamShield Backend - Health Router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import TrustedContact

router = APIRouter()


@router.get("/")
async def root():
    """Welcome endpoint."""
    return {
        "message": "🛡️ Welcome to ScamShield — Real-Time Scam Conversation Detector",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    has_enabled_contact = (
        db.query(TrustedContact.id)
        .filter(TrustedContact.enabled.is_(True))
        .first()
        is not None
    )
    has_legacy_chat = bool(
        settings.TELEGRAM_CHAT_ID
        and settings.TELEGRAM_CHAT_ID != "your_telegram_chat_id"
    )
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "services": {
            "gemini": "configured" if settings.has_gemini_key else "not_configured",
            "sarvam": "configured" if settings.has_sarvam_key else "not_configured",
            "telegram": "configured"
            if settings.has_telegram_bot_token
            and (has_enabled_contact or has_legacy_chat)
            else "not_configured",
        },
    }
