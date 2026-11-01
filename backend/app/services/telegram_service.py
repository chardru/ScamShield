"""
ScamShield Backend - Telegram Notification Service.

Sends security alerts to trusted contacts via Telegram Bot API.
Only sends minimum necessary information — no full transcripts.
"""

import logging
from typing import Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# Telegram embeds its bot token in the request path; suppress HTTPX request-line
# logs so debug logging cannot print that URL.
httpx_logger = logging.getLogger("httpx")
if httpx_logger.level < logging.WARNING:
    httpx_logger.setLevel(logging.WARNING)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
DEFAULT_TEST_MESSAGE = (
    "🛡️ ScamShield Test Notification\n\n"
    "✅ Telegram notifications are configured correctly!\n"
    "You will receive security alerts when high-risk conversations are detected.\n\n"
    "This is a test message from ScamShield."
)


async def _send_message(
    message: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
) -> dict:
    target_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
    if not settings.has_telegram_bot_token or not target_chat_id:
        logger.warning("Telegram bot token or recipient is not configured")
        return {
            "success": False,
            "message": "Telegram bot token or recipient is not configured.",
            "channel": "telegram",
        }

    payload = {
        "chat_id": target_chat_id,
        "text": message,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        url = TELEGRAM_API_URL.format(token=settings.TELEGRAM_BOT_TOKEN)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException:
        logger.warning("Telegram request timed out")
        return {
            "success": False,
            "message": "Telegram request timed out.",
            "channel": "telegram",
        }
    except httpx.HTTPError as error:
        logger.warning("Telegram network request failed (%s)", type(error).__name__)
        return {
            "success": False,
            "message": "Telegram request failed due to a network error.",
            "channel": "telegram",
        }

    if response.status_code != 200:
        logger.warning("Telegram API rejected the request (HTTP %s)", response.status_code)
        return {
            "success": False,
            "message": f"Telegram API rejected the request (HTTP {response.status_code}).",
            "channel": "telegram",
        }

    try:
        result = response.json()
    except ValueError:
        logger.warning("Telegram API returned an invalid response")
        return {
            "success": False,
            "message": "Telegram API returned an invalid response.",
            "channel": "telegram",
        }

    if not isinstance(result, dict) or result.get("ok") is not True:
        logger.warning("Telegram API reported that the message was not delivered")
        return {
            "success": False,
            "message": "Telegram API reported that the message was not delivered.",
            "channel": "telegram",
        }

    return {
        "success": True,
        "message": "Telegram message sent successfully.",
        "channel": "telegram",
    }


async def send_telegram_alert(
    risk_score: int,
    risk_level: str,
    detected_tactics: list,
    recommended_action: str,
    report_id: Optional[str] = None,
    explanation: str = "",
    chat_id: Optional[str] = None,
) -> dict:
    """
    Send a security alert to a selected Telegram chat.
    
    Only sends risk summary — NOT full conversation transcripts.
    """
    tactics = [
        str(tactic).replace("\r", " ").replace("\n", " ")[:120]
        for tactic in detected_tactics[:12]
    ]
    tactics_str = "\n".join(f"• {tactic}" for tactic in tactics) or "• None identified"
    short_explanation = " ".join((explanation or "Suspicious activity detected.").split())[:500]
    short_action = " ".join((recommended_action or "Stop and verify independently.").split())[:500]
    message = (
        "SCAMSHIELD SECURITY ALERT\n\n"
        "A high-risk conversation was detected.\n"
        f"Risk level: {risk_level}\n"
        f"Risk score: {risk_score}/100\n\n"
        f"Detected scam tactics:\n{tactics_str}\n\n"
        f"Explanation: {short_explanation}\n\n"
        f"Recommended safety action: {short_action}\n\n"
        f"Report ID: {report_id or 'N/A'}\n"
        "ScamShield — Real-Time Scam Detector"
    )

    result = await _send_message(message, chat_id=chat_id)
    if result["success"]:
        logger.info("Telegram alert sent for report %s", report_id)
        result["message"] = "Security alert sent successfully"
    return result


async def send_test_notification(
    message: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> dict:
    """Send a test notification to verify Telegram configuration."""
    test_message = message if message is not None else DEFAULT_TEST_MESSAGE
    if not test_message.strip() or len(test_message) > 4096:
        return {
            "success": False,
            "message": "Telegram test message must contain 1 to 4096 characters.",
            "channel": "telegram",
        }

    return await _send_message(test_message, chat_id=chat_id)
