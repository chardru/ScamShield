"""
ScamShield Backend - Report Schemas.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ReportSummary(BaseModel):
    """Summary of an analysis report for listing."""
    id: str
    conversation_text: str
    risk_score: int
    risk_level: str
    is_suspicious: bool
    detected_tactics: List[str] = []
    source: str = "text_input"
    ai_provider: str = "demo"
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ReportDetail(BaseModel):
    """Full detail of an analysis report."""
    id: str
    conversation_text: str
    risk_score: int
    risk_level: str
    is_suspicious: bool
    detected_tactics: List[str] = []
    explanation: str = ""
    recommended_action: str = ""
    confidence: float = 0.0
    source: str = "text_input"
    ai_provider: str = "demo"
    language_detected: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Response containing a list of reports."""
    total: int
    reports: List[ReportSummary]


class NotificationRequest(BaseModel):
    """Request to send a test notification."""
    message: Optional[str] = Field(default=None, min_length=1, max_length=4096)


class NotificationResponse(BaseModel):
    """Response from notification send."""
    success: bool
    message: str
    channel: str = "telegram"
