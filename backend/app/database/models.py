"""
ScamShield Backend - Database Models.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from app.database.database import Base


class AnalysisReport(Base):
    """Stores scam analysis reports."""
    __tablename__ = "analysis_reports"

    id = Column(String, primary_key=True, index=True)
    conversation_text = Column(Text, nullable=False)
    risk_score = Column(Integer, nullable=False, default=0)
    risk_level = Column(String, nullable=False, default="SAFE")
    is_suspicious = Column(Boolean, nullable=False, default=False)
    detected_tactics = Column(JSON, nullable=True)
    explanation = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True, default=0.0)
    source = Column(String, nullable=True, default="text_input")  # text_input, audio, live
    ai_provider = Column(String, nullable=True, default="demo")  # gemini, demo, fallback
    language_detected = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_text": self.conversation_text[:200] + "..." if len(self.conversation_text) > 200 else self.conversation_text,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "is_suspicious": self.is_suspicious,
            "detected_tactics": self.detected_tactics or [],
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "source": self.source,
            "ai_provider": self.ai_provider,
            "language_detected": self.language_detected,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NotificationLog(Base):
    """Logs sent notifications."""
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, nullable=True)
    channel = Column(String, nullable=False, default="telegram")
    status = Column(String, nullable=False, default="pending")  # pending, sent, failed
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TrustedContact(Base):
    """A user-managed Telegram recipient for trusted family alerts."""

    __tablename__ = "trusted_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(80), nullable=False)
    chat_id = Column(String(20), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class NotificationDelivery(Base):
    """Tracks delivery state per Telegram recipient and report."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "recipient_chat_id",
            name="uq_notification_delivery_report_recipient",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, nullable=False, index=True)
    recipient_chat_id = Column(String(20), nullable=False)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
