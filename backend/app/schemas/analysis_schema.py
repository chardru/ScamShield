"""
ScamShield Backend - Analysis Schemas.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class AnalysisRequest(BaseModel):
    """Request body for text analysis."""
    text: str = Field(..., min_length=1, max_length=10000, description="Conversation text to analyze")
    source: str = Field(default="text_input", description="Source of the text: text_input, audio, live")


class TacticDetail(BaseModel):
    """Details about a detected scam tactic."""
    tactic: str
    severity: str = "medium"  # low, medium, high, critical
    evidence: str = ""


class AnalysisResponse(BaseModel):
    """Response from scam analysis."""
    report_id: str
    is_suspicious: bool = False
    risk_score: int = Field(ge=0, le=100)
    risk_level: str  # SAFE, CAUTION, WARNING, DANGER
    detected_tactics: List[str] = []
    tactic_details: List[TacticDetail] = []
    explanation: str = ""
    recommended_action: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    ai_provider: str = "demo"
    source: str = "text_input"


class LiveAnalysisChunk(BaseModel):
    """WebSocket message for live analysis."""
    transcript: str = ""
    risk_score: int = Field(ge=0, le=100, default=0)
    risk_level: str = "SAFE"
    detected_tactics: List[str] = []
    is_final: bool = False


class TranscriptionRequest(BaseModel):
    """Request metadata for audio transcription."""
    language: Optional[str] = None


class TranscriptionResponse(BaseModel):
    """Response from audio transcription."""
    transcript: str
    language_detected: Optional[str] = None
    duration_seconds: Optional[float] = None
    provider: str = "demo"  # sarvam, demo
