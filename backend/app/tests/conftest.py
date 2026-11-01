import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_external_ai_calls_by_default(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(settings, "SARVAM_API_KEY", None)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", None)
