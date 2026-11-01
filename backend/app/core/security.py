"""
ScamShield Backend - Security utilities.
"""

import secrets
import hashlib
from typing import Optional


def generate_report_id() -> str:
    """Generate a unique report ID."""
    return secrets.token_hex(8)


def hash_content(content: str) -> str:
    """Create a SHA-256 hash of content for integrity checking."""
    return hashlib.sha256(content.encode()).hexdigest()


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input text."""
    if not text:
        return ""
    # Truncate to max length
    text = text[:max_length]
    # Remove null bytes
    text = text.replace("\x00", "")
    return text.strip()


def validate_audio_filename(filename: Optional[str]) -> bool:
    """Validate uploaded audio filename."""
    if not filename:
        return False
    allowed_extensions = {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in allowed_extensions
