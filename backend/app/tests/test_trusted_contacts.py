from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.database import init_db
from app.main import app
from app.routers import analysis, notifications

init_db()
client = TestClient(app)


def _chat_id() -> str:
    return f"{100000000000 + uuid4().int % 899999999999}"


def test_trusted_contact_crud_and_duplicate_validation():
    chat_id = _chat_id()
    created = client.post(
        "/api/notifications/contacts",
        json={"name": "  Alex Family  ", "chat_id": chat_id},
    )
    assert created.status_code == 201
    contact = created.json()
    assert contact["name"] == "Alex Family"
    assert contact["chat_id"] == chat_id
    assert contact["enabled"] is True

    listed = client.get("/api/notifications/contacts")
    assert listed.status_code == 200
    assert any(item["id"] == contact["id"] for item in listed.json()["contacts"])

    duplicate = client.post(
        "/api/notifications/contacts",
        json={"name": "Duplicate", "chat_id": chat_id},
    )
    assert duplicate.status_code == 409

    invalid = client.post(
        "/api/notifications/contacts",
        json={"name": "Invalid", "chat_id": "not-a-chat"},
    )
    assert invalid.status_code == 422

    updated = client.put(
        f"/api/notifications/contacts/{contact['id']}",
        json={"name": "Alex Updated", "chat_id": chat_id, "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Alex Updated"
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"/api/notifications/contacts/{contact['id']}")
    assert deleted.status_code == 204
    missing = client.get("/api/notifications/contacts")
    assert all(item["id"] != contact["id"] for item in missing.json()["contacts"])


def test_contact_test_notification_reports_delivery_failure(monkeypatch):
    created = client.post(
        "/api/notifications/contacts",
        json={"name": "Delivery Test", "chat_id": _chat_id(), "enabled": True},
    )
    assert created.status_code == 201
    contact = created.json()

    async def fail_send(*, message=None, chat_id=None):
        assert chat_id == contact["chat_id"]
        raise RuntimeError("private transport detail")

    monkeypatch.setattr(notifications, "send_test_notification", fail_send)
    response = client.post(
        f"/api/notifications/contacts/{contact['id']}/test"
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "start" in response.json()["message"].lower()
    assert "private transport detail" not in response.text

    client.delete(f"/api/notifications/contacts/{contact['id']}")


def test_batch_test_notifies_all_enabled_recipients(monkeypatch):
    chat_ids = [_chat_id(), _chat_id(), _chat_id()]
    contacts = []
    for index, chat_id in enumerate(chat_ids):
        response = client.post(
            "/api/notifications/contacts",
            json={
                "name": f"Batch Contact {index}",
                "chat_id": chat_id,
                "enabled": index != 2,
            },
        )
        assert response.status_code == 201
        contacts.append(response.json())

    delivered_chat_ids = []

    async def succeed(*, message=None, chat_id=None):
        delivered_chat_ids.append(chat_id)
        return {"success": True, "message": "sent", "channel": "telegram"}

    monkeypatch.setattr(notifications, "send_test_notification", succeed)
    response = client.post("/api/notifications/contacts/test")

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["success_count"] == 2
    assert set(delivered_chat_ids) == set(chat_ids[:2])

    for contact in contacts:
        client.delete(f"/api/notifications/contacts/{contact['id']}")


def test_notification_status_never_returns_bot_token(monkeypatch):
    monkeypatch.setattr(
        notifications.settings,
        "TELEGRAM_BOT_TOKEN",
        "do-not-return-this-token",
    )
    response = client.get("/api/notifications/status")

    assert response.status_code == 200
    assert "do-not-return-this-token" not in response.text
    assert "bot_token_set" in response.json()["telegram"]


def test_analysis_succeeds_when_telegram_alert_raises(monkeypatch):
    created = client.post(
        "/api/notifications/contacts",
        json={"name": "Failure Test", "chat_id": _chat_id(), "enabled": True},
    )
    assert created.status_code == 201
    contact = created.json()
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", None)
    monkeypatch.setattr(settings, "TELEGRAM_ALERT_THRESHOLD", 80)

    async def fail_alert(**kwargs):
        raise RuntimeError("private Telegram transport error")

    monkeypatch.setattr(analysis, "send_telegram_alert", fail_alert)
    response = client.post(
        "/api/analyze",
        json={
            "text": (
                "This is the CBI Inspector. You are under digital arrest. "
                "Share your OTP and bank account number immediately. "
                "Transfer Rs 50000 via UPI to our safe account. "
                "Install AnyDesk. Do not tell anyone. You will be arrested."
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["risk_level"] == "DANGER"
    assert "private Telegram transport error" not in response.text
    assert client.delete(
        f"/api/notifications/contacts/{contact['id']}"
    ).status_code == 204
