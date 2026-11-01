import asyncio
from uuid import uuid4

from app.core.config import settings
from app.database.database import SessionLocal, init_db
from app.database.models import NotificationDelivery, NotificationLog, TrustedContact
from app.routers import analysis


def test_alert_threshold_and_report_idempotency(monkeypatch):
    init_db()
    report_id = f"test-{uuid4().hex}"
    sent_alerts = []
    monkeypatch.setattr(settings, "TELEGRAM_ALERT_THRESHOLD", 70)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "test-primary-chat")

    async def fake_send_alert(**kwargs):
        sent_alerts.append(kwargs)
        return {"success": True, "message": "sent", "channel": "telegram"}

    monkeypatch.setattr(analysis, "send_telegram_alert", fake_send_alert)
    with SessionLocal() as db:
        below_threshold = asyncio.run(
            analysis.send_report_alert_once(
                db, report_id, 69, "WARNING", [], "Review the call."
            )
        )
        at_threshold = asyncio.run(
            analysis.send_report_alert_once(
                db, report_id, 70, "WARNING", ["OTP/Password Request"], "Do not share OTPs."
            )
        )
        duplicate = asyncio.run(
            analysis.send_report_alert_once(
                db, report_id, 90, "DANGER", ["OTP/Password Request"], "Do not share OTPs."
            )
        )
        log = (
            db.query(NotificationLog)
            .filter(NotificationLog.report_id == report_id)
            .one()
        )

    assert below_threshold is False
    assert at_threshold is True
    assert duplicate is False
    assert len(sent_alerts) == 1
    assert log.status == "sent"
    assert log.risk_score == 70


def test_failed_alert_is_logged_and_can_be_retried(monkeypatch):
    init_db()
    report_id = f"test-{uuid4().hex}"
    send_attempts = 0
    monkeypatch.setattr(settings, "TELEGRAM_ALERT_THRESHOLD", 80)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "test-primary-chat")

    async def fake_send_alert(**kwargs):
        nonlocal send_attempts
        send_attempts += 1
        if send_attempts == 1:
            raise RuntimeError("transport failure")
        return {"success": True, "message": "sent", "channel": "telegram"}

    monkeypatch.setattr(analysis, "send_telegram_alert", fake_send_alert)
    with SessionLocal() as db:
        first_result = asyncio.run(
            analysis.send_report_alert_once(
                db, report_id, 85, "DANGER", [], "Stop the call."
            )
        )
        retry_result = asyncio.run(
            analysis.send_report_alert_once(
                db, report_id, 85, "DANGER", [], "Stop the call."
            )
        )
        logs = (
            db.query(NotificationLog)
            .filter(NotificationLog.report_id == report_id)
            .order_by(NotificationLog.id)
            .all()
        )

    assert first_result is False
    assert retry_result is True
    assert send_attempts == 2
    assert [entry.status for entry in logs] == ["failed", "sent"]
    assert all(entry.error_message != "transport failure" for entry in logs)


def test_alert_delivers_to_multiple_contacts_and_retries_only_failed_recipient(
    monkeypatch,
):
    init_db()
    report_id = f"test-{uuid4().hex}"
    attempts = []
    contact_a = f"100{uuid4().int % 10**12:012d}"
    contact_b = f"200{uuid4().int % 10**12:012d}"
    monkeypatch.setattr(settings, "TELEGRAM_ALERT_THRESHOLD", 80)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", None)

    async def fake_send_alert(**kwargs):
        attempts.append(kwargs["chat_id"])
        if kwargs["chat_id"] == contact_b and attempts.count(contact_b) == 1:
            return {"success": False, "message": "Delivery failed"}
        return {"success": True, "message": "sent", "channel": "telegram"}

    monkeypatch.setattr(analysis, "send_telegram_alert", fake_send_alert)
    with SessionLocal() as db:
        db.add_all(
            [
                TrustedContact(name="Family A", chat_id=contact_a, enabled=True),
                TrustedContact(name="Family B", chat_id=contact_b, enabled=True),
            ]
        )
        db.commit()

        first_result = asyncio.run(
            analysis.send_report_alert_once(
                db,
                report_id,
                91,
                "DANGER",
                ["Authority Impersonation"],
                "Contact the police directly.",
                "The caller claimed to be a police officer.",
            )
        )
        retry_result = asyncio.run(
            analysis.send_report_alert_once(
                db,
                report_id,
                91,
                "DANGER",
                ["Authority Impersonation"],
                "Contact the police directly.",
                "The caller claimed to be a police officer.",
            )
        )
        duplicate_result = asyncio.run(
            analysis.send_report_alert_once(
                db,
                report_id,
                91,
                "DANGER",
                ["Authority Impersonation"],
                "Contact the police directly.",
                "The caller claimed to be a police officer.",
            )
        )
        delivery_statuses = [
            delivery.status
            for delivery in (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.report_id == report_id)
            .all()
            )
        ]
        db.query(TrustedContact).filter(
            TrustedContact.chat_id.in_([contact_a, contact_b])
        ).delete(synchronize_session=False)
        db.commit()

    assert first_result is True
    assert retry_result is True
    assert duplicate_result is False
    assert attempts == [contact_a, contact_b, contact_b]
    assert set(delivery_statuses) == {"sent"}
