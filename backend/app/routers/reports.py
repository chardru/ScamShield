"""
ScamShield Backend - Reports Router.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.models import AnalysisReport
from app.schemas.report_schema import ReportSummary, ReportDetail, ReportListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Reports"])


@router.get("/reports", response_model=ReportListResponse)
async def list_reports(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    risk_level: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return saved analysis reports with pagination and filtering."""
    query = db.query(AnalysisReport).order_by(AnalysisReport.created_at.desc())

    if risk_level:
        query = query.filter(AnalysisReport.risk_level == risk_level.upper())

    total = query.count()
    reports = query.offset(offset).limit(limit).all()

    return ReportListResponse(
        total=total,
        reports=[
            ReportSummary(
                id=r.id,
                conversation_text=r.conversation_text[:200] + "..." if len(r.conversation_text) > 200 else r.conversation_text,
                risk_score=r.risk_score,
                risk_level=r.risk_level,
                is_suspicious=r.is_suspicious,
                detected_tactics=r.detected_tactics or [],
                source=r.source or "text_input",
                ai_provider=r.ai_provider or "demo",
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in reports
        ],
    )


@router.get("/reports/{report_id}", response_model=ReportDetail)
async def get_report(report_id: str, db: Session = Depends(get_db)):
    """Return a specific analysis report."""
    report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportDetail(
        id=report.id,
        conversation_text=report.conversation_text,
        risk_score=report.risk_score,
        risk_level=report.risk_level,
        is_suspicious=report.is_suspicious,
        detected_tactics=report.detected_tactics or [],
        explanation=report.explanation or "",
        recommended_action=report.recommended_action or "",
        confidence=report.confidence or 0.0,
        source=report.source or "text_input",
        ai_provider=report.ai_provider or "demo",
        language_detected=report.language_detected,
        created_at=report.created_at.isoformat() if report.created_at else None,
    )


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str, db: Session = Depends(get_db)):
    """Delete an analysis report."""
    report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    db.delete(report)
    db.commit()
    return {"message": "Report deleted successfully", "id": report_id}
