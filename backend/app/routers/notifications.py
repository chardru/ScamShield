"""
ScamShield Backend - Notifications Router.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import NotificationLog, TrustedContact
from app.schemas.notification_schema import (
    ContactNotificationTestBatch,
    ContactNotificationTestResult,
    TrustedContactInput,
    TrustedContactListResponse,
    TrustedContactResponse,
)
from app.schemas.report_schema import NotificationRequest, NotificationResponse
from app.services.telegram_service import send_test_notification
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Notifications"])


@router.post("/notifications/test", response_model=NotificationResponse)
async def test_notification(
    request: Optional[NotificationRequest] = None,
    db: Session = Depends(get_db),
):
    """Send a test Telegram notification to verify configuration."""
    result = await send_test_notification(request.message if request else None)

    # Log the notification attempt
    log = NotificationLog(
        channel="telegram",
        status="sent" if result["success"] else "failed",
        error_message=None if result["success"] else result["message"],
    )
    db.add(log)
    db.commit()

    return NotificationResponse(**result)


@router.get(
    "/notifications/contacts",
    response_model=TrustedContactListResponse,
)
async def list_trusted_contacts(db: Session = Depends(get_db)):
    """List trusted family Telegram recipients."""
    contacts = (
        db.query(TrustedContact)
        .order_by(TrustedContact.name, TrustedContact.id)
        .all()
    )
    return TrustedContactListResponse(contacts=contacts)


@router.post(
    "/notifications/contacts",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_trusted_contact(
    request: TrustedContactInput,
    db: Session = Depends(get_db),
):
    """Add a trusted family member."""
    contact = TrustedContact(
        name=request.name,
        chat_id=request.chat_id,
        enabled=request.enabled,
    )
    db.add(contact)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That Telegram Chat ID is already registered.",
        ) from None
    db.refresh(contact)
    return contact


@router.put(
    "/notifications/contacts/{contact_id}",
    response_model=TrustedContactResponse,
)
async def update_trusted_contact(
    contact_id: int,
    request: TrustedContactInput,
    db: Session = Depends(get_db),
):
    """Update a trusted family member."""
    contact = (
        db.query(TrustedContact)
        .filter(TrustedContact.id == contact_id)
        .first()
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Trusted contact not found.")

    contact.name = request.name
    contact.chat_id = request.chat_id
    contact.enabled = request.enabled
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That Telegram Chat ID is already registered.",
        ) from None
    db.refresh(contact)
    return contact


@router.delete(
    "/notifications/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_trusted_contact(
    contact_id: int,
    db: Session = Depends(get_db),
):
    """Remove a trusted family member."""
    contact = (
        db.query(TrustedContact)
        .filter(TrustedContact.id == contact_id)
        .first()
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Trusted contact not found.")
    db.delete(contact)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _test_contact(contact: TrustedContact, db: Session) -> ContactNotificationTestResult:
    message = f"ScamShield test notification for {contact.name}."
    try:
        result = await send_test_notification(
            message=message,
            chat_id=contact.chat_id,
        )
        success = bool(result.get("success"))
        detail = (
            "Test notification sent."
            if success
            else result.get("message", "Telegram could not deliver the test message.")
        )
    except Exception as error:
        logger.warning(
            "Telegram test notification failed for contact %s (%s)",
            contact.id,
            type(error).__name__,
        )
        success = False
        detail = "Telegram test notification failed. Check bot configuration and the recipient's /start status."

    db.add(
        NotificationLog(
            channel="telegram",
            status="sent" if success else "failed",
            error_message=None if success else detail,
        )
    )
    db.commit()
    return ContactNotificationTestResult(
        contact_id=contact.id,
        name=contact.name,
        success=success,
        message=detail,
    )


@router.post(
    "/notifications/contacts/{contact_id}/test",
    response_model=ContactNotificationTestResult,
)
async def test_trusted_contact(
    contact_id: int,
    db: Session = Depends(get_db),
):
    """Send a test message to one trusted family member."""
    contact = (
        db.query(TrustedContact)
        .filter(TrustedContact.id == contact_id)
        .first()
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Trusted contact not found.")
    return await _test_contact(contact, db)


@router.post(
    "/notifications/contacts/test",
    response_model=ContactNotificationTestBatch,
)
async def test_enabled_trusted_contacts(db: Session = Depends(get_db)):
    """Send an individual test message to each enabled trusted contact."""
    contacts = (
        db.query(TrustedContact)
        .filter(TrustedContact.enabled.is_(True))
        .order_by(TrustedContact.id)
        .all()
    )
    results = [await _test_contact(contact, db) for contact in contacts]
    success_count = sum(result.success for result in results)
    return ContactNotificationTestBatch(
        total=len(results),
        success_count=success_count,
        failure_count=len(results) - success_count,
        results=results,
    )


@router.get("/notifications/status")
async def notification_status(db: Session = Depends(get_db)):
    """Check notification configuration status."""
    contact_count = db.query(TrustedContact).count()
    enabled_contact_count = (
        db.query(TrustedContact)
        .filter(TrustedContact.enabled.is_(True))
        .count()
    )
    has_legacy_chat = bool(
        settings.TELEGRAM_CHAT_ID
        and settings.TELEGRAM_CHAT_ID != "your_telegram_chat_id"
    )
    return {
        "telegram": {
            "configured": settings.has_telegram_bot_token
            and (enabled_contact_count > 0 or has_legacy_chat),
            "bot_token_set": settings.has_telegram_bot_token,
            "chat_id_set": has_legacy_chat,
            "contact_count": contact_count,
            "enabled_contact_count": enabled_contact_count,
        },
        "instructions": {
            "step_1": "Create or open the ScamShield bot configured by the primary user.",
            "step_2": "Each family member must open the bot and press Start or send /start before the bot can message them.",
            "step_3": "Have each family member find their numeric Telegram Chat ID using @userinfobot.",
            "step_4": "Add the family member's name and Chat ID in ScamShield Trusted Contacts, then send a test notification.",
        },
    }
