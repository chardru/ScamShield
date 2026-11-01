"""
ScamShield Backend - Analysis Router.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import (
    AnalysisReport,
    NotificationDelivery,
    NotificationLog,
    TrustedContact,
)
from app.schemas.analysis_schema import AnalysisRequest, AnalysisResponse
from app.services.scam_analyzer import analyze_conversation, get_demo_conversations
from app.core.security import generate_report_id, sanitize_input
from app.services.telegram_service import send_telegram_alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analysis"])


async def send_report_alert_once(
    db: Session,
    report_id: str,
    risk_score: int,
    risk_level: str,
    detected_tactics: list,
    recommended_action: str,
    explanation: str = "",
) -> bool:
    """Deliver a report alert once to each enabled Telegram recipient."""
    if risk_score < settings.TELEGRAM_ALERT_THRESHOLD:
        return False

    contacts = (
        db.query(TrustedContact)
        .filter(TrustedContact.enabled.is_(True))
        .order_by(TrustedContact.id)
        .all()
    )
    recipients = {contact.chat_id: contact.name for contact in contacts}
    if settings.has_telegram_config and settings.TELEGRAM_CHAT_ID:
        recipients.setdefault(settings.TELEGRAM_CHAT_ID, "Primary Telegram chat")
    if not settings.has_telegram_bot_token or not recipients:
        logger.warning("Skipping Telegram alert because no bot recipients are configured")
        return False

    latest_notification = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.report_id == report_id,
            NotificationLog.channel == "telegram",
        )
        .order_by(NotificationLog.id.desc())
        .first()
    )
    if latest_notification and latest_notification.status in ("pending", "sent"):
        logger.info("Skipping duplicate Telegram alert for report %s", report_id)
        return False

    notification = NotificationLog(
        report_id=report_id,
        channel="telegram",
        status="pending",
        risk_score=risk_score,
        risk_level=risk_level,
    )
    db.add(notification)
    db.commit()

    all_succeeded = True
    any_succeeded = False
    for recipient_chat_id in recipients:
        delivery = (
            db.query(NotificationDelivery)
            .filter(
                NotificationDelivery.report_id == report_id,
                NotificationDelivery.recipient_chat_id == recipient_chat_id,
            )
            .first()
        )
        if delivery and delivery.status in ("pending", "sent"):
            all_succeeded = all_succeeded and delivery.status == "sent"
            any_succeeded = any_succeeded or delivery.status == "sent"
            continue

        if delivery is None:
            delivery = NotificationDelivery(
                report_id=report_id,
                recipient_chat_id=recipient_chat_id,
                status="pending",
            )
            db.add(delivery)
        else:
            delivery.status = "pending"
            delivery.error_message = None
        db.commit()

        try:
            result = await send_telegram_alert(
                risk_score=risk_score,
                risk_level=risk_level,
                detected_tactics=detected_tactics,
                explanation=explanation,
                recommended_action=recommended_action,
                report_id=report_id,
                chat_id=recipient_chat_id,
            )
            delivered = bool(result.get("success"))
            delivery.error_message = (
                None if delivered else "Telegram alert delivery failed."
            )
        except Exception as error:
            logger.warning(
                "Telegram alert failed for report %s (%s)",
                report_id,
                type(error).__name__,
            )
            delivered = False
            delivery.error_message = "Telegram alert delivery failed."

        delivery.status = "sent" if delivered else "failed"
        any_succeeded = any_succeeded or delivered
        all_succeeded = all_succeeded and delivered
        db.commit()

    notification.status = "sent" if all_succeeded else "failed"
    notification.error_message = (
        None if all_succeeded else "One or more Telegram alerts failed."
    )
    db.commit()
    return any_succeeded


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_text(request: AnalysisRequest, db: Session = Depends(get_db)):
    """
    Analyze conversation text for scam indicators.
    
    Combines AI analysis with deterministic pattern matching.
    Saves reports and sends Telegram alerts at the configured risk threshold.
    """
    text = sanitize_input(request.text)
    if not text:
        raise HTTPException(status_code=400, detail="Conversation text cannot be empty")

    try:
        result = await analyze_conversation(text, source=request.source)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis service error")

    # Save to database
    report_id = generate_report_id()
    report = AnalysisReport(
        id=report_id,
        conversation_text=text,
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        is_suspicious=result["is_suspicious"],
        detected_tactics=result["detected_tactics"],
        explanation=result["explanation"],
        recommended_action=result["recommended_action"],
        confidence=result["confidence"],
        source=result["source"],
        ai_provider=result["ai_provider"],
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    await send_report_alert_once(
        db=db,
        report_id=report_id,
        risk_score=result["risk_score"],
        risk_level=result["risk_level"],
        detected_tactics=result["detected_tactics"],
        recommended_action=result["recommended_action"],
        explanation=result["explanation"],
    )

    return AnalysisResponse(
        report_id=report_id,
        **result,
    )


@router.get("/demo-conversations")
async def list_demo_conversations():
    """Return demo conversation samples for testing."""
    return {"conversations": get_demo_conversations()}
