"""
ScamShield Backend - WebSocket Router for Live Monitoring.
"""
import asyncio
import base64
import json
import logging
from app.services.sarvam_realtime import connect_sarvam_realtime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.scam_analyzer import analyze_conversation
from app.services.risk_engine import get_risk_level
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
MAX_AUDIO_PACKET_BYTES = 64 * 1024


def _sarvam_error_message(error: Exception) -> str:
    if not settings.has_sarvam_key:
        return (
            "Sarvam real-time transcription is not configured. "
            "Set SARVAM_API_KEY in the backend environment."
        )

    response = getattr(error, "response", None)
    http_status = getattr(response, "status_code", None)
    if http_status in (401, 403):
        return "Sarvam authentication failed. Verify the backend API key."
    if http_status == 429:
        return "Sarvam rate limit or quota reached. Try again later."
    if http_status is not None and http_status >= 500:
        return "Sarvam real-time transcription is temporarily unavailable."

    close_code = getattr(error, "code", None)
    if close_code == 1003:
        return (
            "Sarvam rejected the session because of an invalid key or quota limit. "
            "Check the backend key and account usage."
        )
    if close_code == 1008:
        return "Sarvam closed an inactive session. Restart monitoring and speak."
    if close_code == 1011:
        return "Sarvam encountered a service error. Try again shortly."
    if close_code == 4000:
        return "Sarvam rejected the model or language configuration."
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return "Timed out connecting to Sarvam real-time transcription."
    return (
        "Could not connect to Sarvam real-time transcription. "
        "Check the backend network and Sarvam service status."
    )


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
        
@router.websocket("/ws/session/{session_id}")
async def websocket_live_session(websocket: WebSocket, session_id: str):
    """
    Live audio session:
    Flutter binary PCM -> FastAPI -> Sarvam Realtime STT
    -> transcript -> Scam Analyzer -> risk update.
    """
    await manager.connect(websocket)
    sarvam_ws = None
    sender_task = None
    receiver_task = None

    transcript = ""
    current_score = 0
    current_level = "SAFE"
    detected_tactics = set()

    try:
        try:
            raw_start = await asyncio.wait_for(websocket.receive_text(), timeout=15)
            start = json.loads(raw_start)
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "message": "Timed out waiting for live audio configuration.",
            })
            await websocket.close(code=1008)
            return
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "message": "Live audio configuration must be valid JSON.",
            })
            await websocket.close(code=1008)
            return

        if not isinstance(start, dict) or start.get("type") != "start":
            await websocket.send_json({
                "type": "error",
                "message": "First message must have type=start."
            })
            await websocket.close(code=1008)
            return

        language = start.get("call_language", "auto")
        if not isinstance(language, str):
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported call language.",
            })
            await websocket.close(code=1008)
            return
        language_aliases = {
            "ta": "ta-IN",
            "en": "en-IN",
            "hi": "hi-IN",
        }
        language = language_aliases.get(language, language)

        if not isinstance(language, str) or language not in {
            "auto",
            "ta-IN",
            "en-IN",
            "hi-IN",
        }:
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported call language."
            })
            await websocket.close(code=1008)
            return

        source = start.get("source", "mic")
        if not isinstance(source, str) or source not in {"mic", "tab", "file"}:
            await websocket.send_json({
                "type": "error",
                "message": "Unsupported audio source."
            })
            await websocket.close(code=1008)
            return

        alert_langs = start.get("alert_langs", ["ta", "en"])
        if (
            not isinstance(alert_langs, list)
            or not all(isinstance(item, str) for item in alert_langs)
        ):
            await websocket.send_json({
                "type": "error",
                "message": "alert_langs must be a list of language codes.",
            })
            await websocket.close(code=1008)
            return

        try:
            sarvam_ws = await connect_sarvam_realtime(language)
        except Exception as error:
            logger.warning(
                "Sarvam realtime connection failed for session %s (%s)",
                session_id,
                type(error).__name__,
            )
            await websocket.send_json({
                "type": "stt_error",
                "code": getattr(
                    getattr(error, "response", None),
                    "status_code",
                    None,
                ),
                "message": _sarvam_error_message(error),
                "fatal": True,
            })
            await websocket.close(code=1011)
            return

        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "source": source,
            "call_language": language,
            "platform": start.get("platform"),
            "message": "Live audio transcription connected.",
        })

        async def send_audio_to_sarvam():
            """Receive binary PCM chunks from Flutter and forward them."""
            while True:
                packet = await websocket.receive()

                if packet["type"] == "websocket.disconnect":
                    await sarvam_ws.send(json.dumps({"event": "end"}))
                    return

                audio_bytes = packet.get("bytes")

                if audio_bytes is not None:
                    if (
                        not audio_bytes
                        or len(audio_bytes) % 2 != 0
                        or len(audio_bytes) > MAX_AUDIO_PACKET_BYTES
                    ):
                        await websocket.send_json({
                            "type": "error",
                            "message": (
                                "Invalid PCM audio packet. Send non-empty "
                                "16-bit mono audio chunks no larger than 64 KB."
                            ),
                        })
                        await sarvam_ws.send(json.dumps({"event": "end"}))
                        return

                    encoded_audio = base64.b64encode(
                        audio_bytes
                    ).decode("ascii")

                    await sarvam_ws.send(json.dumps({
                        "event": "audio_input",
                        "audio": encoded_audio
                    }))

                text_message = packet.get("text")

                if text_message:
                    try:
                        control = json.loads(text_message)
                    except json.JSONDecodeError:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Control messages must be valid JSON.",
                        })
                        await sarvam_ws.send(json.dumps({"event": "end"}))
                        return

                    if not isinstance(control, dict):
                        await websocket.send_json({
                            "type": "error",
                            "message": "Control messages must be JSON objects.",
                        })
                        await sarvam_ws.send(json.dumps({"event": "end"}))
                        return

                    if control.get("type") == "stop":
                        await sarvam_ws.send(json.dumps({"event": "end"}))
                        return

                    if control.get("type") == "ping":
                        await sarvam_ws.send(json.dumps({"event": "ping"}))
                        await websocket.send_json({"type": "pong"})
                        continue

                    await websocket.send_json({
                        "type": "error",
                        "message": "Unsupported live audio control message.",
                    })
                    await sarvam_ws.send(json.dumps({"event": "end"}))
                    return

                if audio_bytes is None and not text_message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Unsupported live audio WebSocket message.",
                    })
                    await sarvam_ws.send(json.dumps({"event": "end"}))
                    return

        async def receive_sarvam_transcripts():
            """Receive Sarvam events and send transcript/risk updates."""
            nonlocal transcript, current_score, current_level

            async for raw_event in sarvam_ws:
                try:
                    event = json.loads(raw_event)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Ignoring malformed Sarvam event for session %s", session_id)
                    continue

                if not isinstance(event, dict):
                    logger.warning("Ignoring invalid Sarvam event for session %s", session_id)
                    continue

                event_type = event.get("event")

                if event_type == "session.begin":
                    await websocket.send_json({
                        "type": "stt_ready",
                        "provider": "sarvam",
                        "session_id": session_id,
                    })

                elif event_type == "transcript.partial":
                    partial_text = event.get("text")
                    if isinstance(partial_text, str):
                        await websocket.send_json({
                            "type": "transcript_partial",
                            "text": partial_text,
                            "language": event.get("language"),
                        })

                elif event_type == "transcript.final":
                    sentence = event.get("text")
                    if not isinstance(sentence, str) or not sentence.strip():
                        await websocket.send_json({
                            "type": "transcription_notice",
                            "message": "No speech was recognized in that audio segment.",
                        })
                        continue

                    sentence = sentence.strip()
                    transcript = f"{transcript} {sentence}".strip()

                    await websocket.send_json({
                        "type": "transcript_final",
                        "text": sentence,
                        "transcript": transcript,
                        "language": event.get("language"),
                    })

                    try:
                        result = await analyze_conversation(
                            transcript,
                            source="live",
                        )

                        new_score = int(result.get("risk_score", 0))
                        if current_level in {"WARNING", "DANGER"}:
                            current_score = max(current_score, new_score)
                        else:
                            current_score = new_score

                        current_level = get_risk_level(current_score)
                        detected_tactics.update(
                            result.get("detected_tactics", [])
                        )

                        await websocket.send_json({
                            "type": "analysis_update",
                            "session_id": session_id,
                            "transcript": transcript,
                            "risk_score": current_score,
                            "risk_level": current_level,
                            "detected_tactics": sorted(detected_tactics),
                            "is_suspicious": current_score >= 30,
                            "explanation": result.get("explanation", ""),
                            "recommended_action": result.get(
                                "recommended_action", ""
                            ),
                            "is_final": True,
                        })

                    except Exception as error:
                        logger.warning(
                            "Live transcript analysis failed for session %s (%s)",
                            session_id,
                            type(error).__name__,
                        )
                        await websocket.send_json({
                            "type": "analysis_error",
                            "message": (
                                "Analysis is temporarily unavailable. "
                                "The transcript is still available."
                            ),
                        })

                elif event_type == "error":
                    await websocket.send_json({
                        "type": "stt_error",
                        "code": event.get("code"),
                        "message": event.get(
                            "message",
                            "Speech recognition service returned an error.",
                        ),
                        "fatal": event.get("is_fatal", False),
                    })

                    if event.get("is_fatal", False):
                        return

                elif event_type == "session.end":
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                        "transcript": transcript,
                        "risk_score": current_score,
                        "risk_level": current_level,
                    })
                    return

        sender_task = asyncio.create_task(send_audio_to_sarvam())
        receiver_task = asyncio.create_task(receive_sarvam_transcripts())

        done, pending = await asyncio.wait(
            {sender_task, receiver_task},
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            task.result()

        if sender_task in done and receiver_task not in done:
            try:
                await asyncio.wait_for(receiver_task, timeout=5)
            except asyncio.TimeoutError:
                receiver_task.cancel()

        elif receiver_task in done and sender_task not in done:
            await websocket.close(code=1000)

    except WebSocketDisconnect:
        logger.info("Live audio client disconnected: %s", session_id)

    except Exception as error:
        logger.warning(
            "Live audio session failed for %s (%s)",
            session_id,
            type(error).__name__,
        )
        try:
            await websocket.send_json({
                "type": "session_error",
                "message": _sarvam_error_message(error),
            })
        except WebSocketDisconnect:
            pass

    finally:
        for task in (sender_task, receiver_task):
            if task and not task.done():
                task.cancel()

        tasks = [
            task for task in (sender_task, receiver_task)
            if task is not None
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        if sarvam_ws is not None:
            try:
                await sarvam_ws.close()
            except Exception as error:
                logger.warning(
                    "Sarvam socket cleanup failed for %s (%s)",
                    session_id,
                    type(error).__name__,
                )

        manager.disconnect(websocket)
