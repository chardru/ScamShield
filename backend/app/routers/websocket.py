"""
ScamShield Backend - WebSocket Router for Live Monitoring.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.scam_analyzer import analyze_conversation
from app.services.risk_engine import get_risk_level

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live_analysis(websocket: WebSocket):
    """
    WebSocket endpoint for live conversation monitoring.
    
    Receives transcript chunks, analyzes them, and returns:
    - Updated transcript
    - Risk score
    - Risk level
    - Detected tactics
    """
    await manager.connect(websocket)
    accumulated_transcript = ""

    try:
        while True:
            # Receive transcript chunk
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                chunk = message.get("text", "")
                is_final = message.get("is_final", False)
            except json.JSONDecodeError:
                chunk = data
                is_final = False

            if chunk:
                accumulated_transcript += " " + chunk if accumulated_transcript else chunk

            # Analyze accumulated transcript
            if accumulated_transcript.strip():
                result = await analyze_conversation(accumulated_transcript, source="live")

                await manager.send_json(websocket, {
                    "type": "analysis_update",
                    "transcript": accumulated_transcript,
                    "risk_score": result["risk_score"],
                    "risk_level": result["risk_level"],
                    "detected_tactics": result["detected_tactics"],
                    "is_suspicious": result["is_suspicious"],
                    "explanation": result["explanation"],
                    "is_final": is_final,
                })

            if is_final:
                await manager.send_json(websocket, {
                    "type": "analysis_complete",
                    "transcript": accumulated_transcript,
                    "risk_score": result["risk_score"] if accumulated_transcript.strip() else 0,
                    "risk_level": result["risk_level"] if accumulated_transcript.strip() else "SAFE",
                    "detected_tactics": result.get("detected_tactics", []) if accumulated_transcript.strip() else [],
                })
                accumulated_transcript = ""

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from live monitoring")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
