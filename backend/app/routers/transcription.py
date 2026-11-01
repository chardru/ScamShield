"""
ScamShield Backend - Transcription Router.
"""

import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Optional

from app.schemas.analysis_schema import TranscriptionResponse
from app.services.sarvam_service import transcribe_audio, get_demo_transcription
from app.core.config import settings
from app.core.security import validate_audio_filename

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Transcription"])


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
):
    """
    Upload an audio file for speech-to-text transcription.
    
    Supports: WAV, MP3, OGG, M4A, FLAC, WebM
    Max size: configurable (default 25MB)
    """
    # Validate filename
    if not validate_audio_filename(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported audio format. Supported: WAV, MP3, OGG, M4A, FLAC, WebM",
        )

    # Check file size
    max_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Maximum size: {settings.MAX_AUDIO_SIZE_MB}MB",
        )

    # Save temporarily
    os.makedirs(settings.TEMP_AUDIO_DIR, exist_ok=True)
    temp_path = os.path.join(settings.TEMP_AUDIO_DIR, file.filename)

    try:
        with open(temp_path, "wb") as f:
            f.write(content)

        result = await transcribe_audio(temp_path, language=language)

        if "error" in result:
            raise HTTPException(
                status_code=502,
                detail=f"Transcription service error: {result['error']}",
            )

        return TranscriptionResponse(
            transcript=result.get("transcript", ""),
            language_detected=result.get("language_detected"),
            provider=result.get("provider", "demo"),
        )

    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/transcription-status")
async def transcription_status():
    """Check if transcription service is available."""
    return {
        "sarvam_configured": settings.has_sarvam_key,
        "demo_available": True,
        "supported_formats": ["wav", "mp3", "ogg", "m4a", "flac", "webm"],
        "max_size_mb": settings.MAX_AUDIO_SIZE_MB,
    }
