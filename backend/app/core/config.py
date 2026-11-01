"""
ScamShield Backend - Configuration Module
Loads environment variables using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "ScamShield"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./scamshield.db"

    # API Keys
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_READ_TIMEOUT_SECONDS: float = Field(default=60.0, ge=5.0, le=120.0)
    SARVAM_API_KEY: Optional[str] = None

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_ALERT_THRESHOLD: int = Field(default=80, ge=0, le=100)

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:8000,http://localhost:5000"

    # Audio
    MAX_AUDIO_SIZE_MB: int = 25
    TEMP_AUDIO_DIR: str = "temp_audio"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY != "your_gemini_api_key")

    @property
    def has_sarvam_key(self) -> bool:
        return bool(self.SARVAM_API_KEY and self.SARVAM_API_KEY != "your_sarvam_api_key")

    @property
    def has_telegram_config(self) -> bool:
        return bool(
            self.has_telegram_bot_token
            and self.TELEGRAM_CHAT_ID
            and self.TELEGRAM_CHAT_ID != "your_telegram_chat_id"
        )

    @property
    def has_telegram_bot_token(self) -> bool:
        return bool(
            self.TELEGRAM_BOT_TOKEN
            and self.TELEGRAM_BOT_TOKEN != "your_telegram_bot_token"
        )

    class Config:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
