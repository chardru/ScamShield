"""
ScamShield Sarvam AI speech-to-text service.
"""

import logging
import os
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_MODEL = "saaras:v4"
SUPPORTED_LANGUAGES = {"ta-IN", "en-IN"}


async def transcribe_audio(
    file_path: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Transcribe an audio file through Sarvam's REST API."""
    if not settings.has_sarvam_key:
        logger.info("Sarvam API key not configured — returning demo transcript")
        return get_demo_transcription()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    if language is not None and language not in SUPPORTED_LANGUAGES:
        return {
            "transcript": "",
            "language_detected": None,
            "provider": "sarvam",
            "error": "Unsupported language. Use ta-IN, en-IN, or omit for automatic detection.",
        }

    data = {"model": SARVAM_MODEL}
    if language:
        data["language_code"] = language

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, "rb") as audio_file:
                response = await client.post(
                    SARVAM_API_URL,
                    headers={"api-subscription-key": settings.SARVAM_API_KEY},
                    files={"file": (os.path.basename(file_path), audio_file)},
                    data=data,
                )
    except httpx.TimeoutException:
        logger.warning("Sarvam request timed out")
        return _transcription_error("Transcription request timed out.")
    except httpx.HTTPError as error:
        logger.warning("Sarvam network request failed (%s)", type(error).__name__)
        return _transcription_error("Transcription request failed due to a network error.")
    except OSError:
        logger.exception("Could not read the audio file for transcription")
        raise

    if response.status_code != 200:
        if response.status_code in (401, 403):
            logger.warning("Sarvam authentication failed (HTTP %s)", response.status_code)
            message = "Sarvam authentication failed. Check SARVAM_API_KEY."
        elif response.status_code == 429:
            logger.warning("Sarvam rate limit exceeded")
            message = "Sarvam rate limit exceeded. Try again later."
        elif response.status_code >= 500:
            logger.warning("Sarvam service unavailable (HTTP %s)", response.status_code)
            message = "Sarvam transcription service is temporarily unavailable."
        else:
            logger.warning("Sarvam rejected the transcription request (HTTP %s)", response.status_code)
            message = f"Sarvam rejected the transcription request (HTTP {response.status_code})."
        return _transcription_error(message)

    try:
        result = response.json()
    except ValueError:
        logger.warning("Sarvam returned an invalid response")
        return _transcription_error("Sarvam returned an invalid response.")

    transcript = result.get("transcript") if isinstance(result, dict) else None
    detected_language = result.get("language_code") if isinstance(result, dict) else None
    if not isinstance(transcript, str) or not isinstance(detected_language, (str, type(None))):
        logger.warning("Sarvam response did not match the expected schema")
        return _transcription_error("Sarvam returned an invalid transcription response.")

    return {
        "transcript": transcript,
        "language_detected": detected_language,
        "provider": "sarvam",
    }


def _transcription_error(message: str) -> Dict[str, Any]:
    return {
        "transcript": "",
        "language_detected": None,
        "provider": "sarvam",
        "error": message,
    }


def get_demo_transcription() -> Dict[str, Any]:
    """Return a demo transcription when no Sarvam API key is configured."""
    return {
        "transcript": (
            "Hello, this is a sample transcription from demo mode. "
            "Sarvam AI API key is not configured. To enable real speech-to-text, "
            "set SARVAM_API_KEY in your .env file. "
            "You can still test the application using manual text input or demo conversations."
        ),
        "language_detected": "en",
        "provider": "demo",
    }
