import asyncio
import base64
import json
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.routers import websocket as websocket_router
from app.services import sarvam_realtime


class MockSarvamWebSocket:
    def __init__(self, transcripts=None):
        self._events = asyncio.Queue()
        self._events.put_nowait(json.dumps({"event": "session.begin"}))
        self._transcripts = iter(transcripts or ["Recognized speech."])
        self.sent_events = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self._events.get()
        if event is None:
            raise StopAsyncIteration
        return event

    async def send(self, raw_event):
        event = json.loads(raw_event)
        self.sent_events.append(event)
        if event.get("event") == "audio_input":
            transcript = next(self._transcripts)
            await self._events.put(json.dumps({
                "event": "transcript.partial",
                "text": transcript[:10],
            }))
            await self._events.put(json.dumps({
                "event": "transcript.final",
                "text": transcript,
                "language": "en-IN",
            }))
        elif event.get("event") == "end":
            await self._events.put(json.dumps({
                "event": "session.end",
                "audio_duration_s": 0.2,
            }))
            await self._events.put(None)

    async def close(self):
        self.closed = True


def _read_until(websocket, message_type, count=1):
    found = []
    while len(found) < count:
        message = websocket.receive_json()
        if message.get("type") == message_type:
            found.append(message)
    return found


def test_live_audio_session_forwards_pcm_and_transcript(monkeypatch):
    mock_sarvam = MockSarvamWebSocket()
    connected_languages = []

    async def fake_connect(language):
        connected_languages.append(language)
        return mock_sarvam

    async def fake_analyze(text, source):
        assert text == "Recognized speech."
        assert source == "live"
        return {
            "risk_score": 65,
            "risk_level": "WARNING",
            "detected_tactics": ["Urgency and Pressure"],
            "explanation": "A pressure tactic was detected.",
            "recommended_action": "Pause and verify independently.",
        }

    monkeypatch.setattr(settings, "SARVAM_API_KEY", "unit-test-key")
    monkeypatch.setattr(websocket_router, "connect_sarvam_realtime", fake_connect)
    monkeypatch.setattr(websocket_router, "analyze_conversation", fake_analyze)

    with TestClient(app).websocket_connect("/ws/session/test-session") as client:
        client.send_json({
            "type": "start",
            "call_language": "en",
            "alert_langs": ["ta", "en"],
            "source": "mic",
            "platform": "web",
        })

        assert client.receive_json()["type"] == "session_started"
        assert client.receive_json()["type"] == "stt_ready"
        client.send_bytes(b"\x01\x00" * 1600)

        assert client.receive_json()["type"] == "transcript_partial"
        final = client.receive_json()
        assert final["type"] == "transcript_final"
        assert final["text"] == "Recognized speech."
        analysis = client.receive_json()
        assert analysis["type"] == "analysis_update"
        assert analysis["risk_score"] == 65
        assert analysis["risk_level"] == "WARNING"
        assert analysis["detected_tactics"] == ["Urgency and Pressure"]

        client.send_json({"type": "stop"})
        ended = client.receive_json()
        assert ended["type"] == "session_ended"
        assert ended["transcript"] == "Recognized speech."

    audio_event = next(
        event for event in mock_sarvam.sent_events
        if event.get("event") == "audio_input"
    )
    assert base64.b64decode(audio_event["audio"]) == b"\x01\x00" * 1600
    assert connected_languages == ["en-IN"]
    assert mock_sarvam.closed


def test_live_audio_risk_cannot_fall_after_warning(monkeypatch):
    mock_sarvam = MockSarvamWebSocket(["First warning.", "Second safe sentence."])
    scores = iter((60, 20))

    async def fake_connect(_language):
        return mock_sarvam

    async def fake_analyze(_text, source):
        assert source == "live"
        score = next(scores)
        return {
            "risk_score": score,
            "detected_tactics": [],
            "explanation": "Test analysis.",
            "recommended_action": "Verify independently.",
        }

    monkeypatch.setattr(settings, "SARVAM_API_KEY", "unit-test-key")
    monkeypatch.setattr(websocket_router, "connect_sarvam_realtime", fake_connect)
    monkeypatch.setattr(websocket_router, "analyze_conversation", fake_analyze)

    with TestClient(app).websocket_connect("/ws/session/monotonic-risk") as client:
        client.send_json({"type": "start", "call_language": "auto"})
        client.receive_json()
        client.receive_json()

        updates = []
        for _ in range(2):
            client.send_bytes(b"\x00\x00" * 1600)
            updates.extend(_read_until(client, "analysis_update"))
        assert [update["risk_score"] for update in updates] == [60, 60]
        assert [update["risk_level"] for update in updates] == [
            "WARNING",
            "WARNING",
        ]

        client.send_json({"type": "stop"})
        assert client.receive_json()["type"] == "session_ended"


def test_live_audio_rejects_invalid_pcm_packet(monkeypatch):
    mock_sarvam = MockSarvamWebSocket()

    async def fake_connect(_language):
        return mock_sarvam

    monkeypatch.setattr(settings, "SARVAM_API_KEY", "unit-test-key")
    monkeypatch.setattr(websocket_router, "connect_sarvam_realtime", fake_connect)

    with TestClient(app).websocket_connect("/ws/session/invalid-pcm") as client:
        client.send_json({"type": "start"})
        client.receive_json()
        client.receive_json()
        client.send_bytes(b"\x01")

        error = client.receive_json()
        assert error["type"] == "error"
        assert "Invalid PCM" in error["message"]
        assert client.receive_json()["type"] == "session_ended"

    assert not any(
        event.get("event") == "audio_input"
        for event in mock_sarvam.sent_events
    )


def test_live_audio_rejects_invalid_start_without_connecting(monkeypatch):
    connected = False

    async def fake_connect(_language):
        nonlocal connected
        connected = True
        raise AssertionError("Invalid configuration must not connect.")

    monkeypatch.setattr(websocket_router, "connect_sarvam_realtime", fake_connect)

    with TestClient(app).websocket_connect("/ws/session/bad-start") as client:
        client.send_text("{")
        error = client.receive_json()
        assert error["type"] == "error"
        assert "valid JSON" in error["message"]

    assert not connected


def test_live_audio_reports_sarvam_authentication_failure(monkeypatch):
    class AuthenticationFailure(Exception):
        response = type("Response", (), {"status_code": 401})()

    async def fail_connect(_language):
        raise AuthenticationFailure()

    monkeypatch.setattr(settings, "SARVAM_API_KEY", "unit-test-key")
    monkeypatch.setattr(websocket_router, "connect_sarvam_realtime", fail_connect)

    with TestClient(app).websocket_connect("/ws/session/auth-failure") as client:
        client.send_json({"type": "start"})
        error = client.receive_json()
        assert error["type"] == "stt_error"
        assert error["code"] == 401
        assert "authentication failed" in error["message"].lower()
        assert error["fatal"] is True


def test_sarvam_realtime_connection_uses_documented_endpoint(monkeypatch):
    captured = {}
    fake_connection = object()

    async def fake_websocket_connect(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return fake_connection

    monkeypatch.setattr(settings, "SARVAM_API_KEY", "unit-test-key")
    monkeypatch.setattr(
        sarvam_realtime.websockets,
        "connect",
        fake_websocket_connect,
    )

    connection = asyncio.run(sarvam_realtime.connect_sarvam_realtime("ta-IN"))

    parsed_url = urlparse(captured["url"])
    query = parse_qs(parsed_url.query)
    assert connection is fake_connection
    assert parsed_url.scheme == "wss"
    assert parsed_url.netloc == "api.sarvam.ai"
    assert parsed_url.path == "/speech-to-text-realtime/ws"
    assert query == {
        "language_code": ["ta-IN"],
        "model": ["saaras:v3-realtime"],
        "stream_type": ["fast"],
        "encoding": ["linear16"],
        "sample_rate": ["16000"],
        "endpointing": ["vad"],
    }
    assert captured["kwargs"]["extra_headers"] == {
        "api-subscription-key": "unit-test-key",
    }
    assert captured["kwargs"]["open_timeout"] == 15
