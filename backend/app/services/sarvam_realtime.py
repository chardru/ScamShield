
"""
ScamShield - Sarvam Realtime Speech-to-Text WebSocket service.
"""

from urllib.parse import urlencode

import websockets

from app.core.config import settings


SARVAM_REALTIME_URL = "wss://api.sarvam.ai/speech-to-text-realtime/ws"

SUPPORTED_LANGUAGES = {
    "auto",
    "ta-IN",
    "en-IN",
    "hi-IN",
}


async def connect_sarvam_realtime(language_code: str = "auto"):
    """
    Connect to Sarvam's realtime STT WebSocket.

    Incoming audio must be mono, 16 kHz, 16-bit Linear PCM.
    """

    if not settings.has_sarvam_key:
        raise RuntimeError("Sarvam API key is not configured.")

    if language_code not in SUPPORTED_LANGUAGES:
        raise ValueError(
            "Unsupported language. Use auto, ta-IN, en-IN, or hi-IN."
        )

    query = urlencode({
        "language_code": language_code,
        "model": "saaras:v3-realtime",
        "stream_type": "fast",
        "encoding": "linear16",
        "sample_rate": 16000,
        "endpointing": "vad",
    })

    url = f"{SARVAM_REALTIME_URL}?{query}"

    return await websockets.connect(
        url,
        extra_headers={
            "api-subscription-key": settings.SARVAM_API_KEY,
        },
        open_timeout=15,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=10,
        max_size=2**20,
    )
