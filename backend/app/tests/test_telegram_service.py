import asyncio
import logging

import httpx
import pytest

from app.core.config import settings
from app.services import telegram_service


class FakeResponse:
    def __init__(self, status_code=200, result=None):
        self.status_code = status_code
        self.result = result if result is not None else {"ok": True}

    def json(self):
        return self.result


class FakeAsyncClient:
    response = FakeResponse()
    error = None
    request_payload = None

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, json):
        type(self).request_payload = json
        if type(self).error:
            raise type(self).error
        return type(self).response


@pytest.fixture
def configured_telegram(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "test-chat")
    monkeypatch.setattr(telegram_service.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeResponse()
    FakeAsyncClient.error = None
    FakeAsyncClient.request_payload = None


def test_test_notification_sends_exact_message(configured_telegram):
    message = "ScamShield Telegram Integration Successful!"

    result = asyncio.run(telegram_service.send_test_notification(message))

    assert result["success"] is True
    assert FakeAsyncClient.request_payload == {
        "chat_id": "test-chat",
        "text": message,
    }


def test_test_notification_reports_http_error_without_response_body(configured_telegram):
    FakeAsyncClient.response = FakeResponse(status_code=403, result={"description": "private error"})

    result = asyncio.run(telegram_service.send_test_notification("test"))

    assert result["success"] is False
    assert "403" in result["message"]
    assert "private error" not in result["message"]


def test_alert_includes_safety_summary_and_targets_recipient(configured_telegram):
    result = asyncio.run(
        telegram_service.send_telegram_alert(
            risk_score=92,
            risk_level="DANGER",
            detected_tactics=["Authority impersonation", "OTP request"],
            explanation="The caller threatened arrest and requested a verification code.",
            recommended_action="Hang up and call the official police number.",
            report_id="report-safe-id",
            chat_id="family-chat",
        )
    )

    sent = FakeAsyncClient.request_payload
    assert result["success"] is True
    assert sent["chat_id"] == "family-chat"
    assert "DANGER" in sent["text"]
    assert "92/100" in sent["text"]
    assert "Authority impersonation" in sent["text"]
    assert "threatened arrest" in sent["text"]
    assert "official police number" in sent["text"]
    assert "parse_mode" not in sent


def test_test_notification_handles_telegram_api_rejection(configured_telegram):
    FakeAsyncClient.response = FakeResponse(result={"ok": False, "description": "chat not found"})

    result = asyncio.run(telegram_service.send_test_notification("test"))

    assert result["success"] is False
    assert "not delivered" in result["message"]


def test_test_notification_handles_network_error_without_url(configured_telegram):
    FakeAsyncClient.error = httpx.ConnectError("request failed for bot-token URL")

    result = asyncio.run(telegram_service.send_test_notification("test"))

    assert result["success"] is False
    assert "bot-token" not in result["message"]
    assert "network error" in result["message"]


def test_telegram_http_request_logs_are_suppressed():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
