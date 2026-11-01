import asyncio
import json

import httpx

from app.core.config import settings
from app.services import gemini_service, sarvam_service
from app.services import scam_analyzer
from app.services.risk_engine import (
    analyze_text_deterministic,
    combine_scores,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, events=None):
        self.status_code = status_code
        self.payload = payload if payload is not None else {}
        self.events = events or ([self.payload] if self.payload else [])

    def json(self):
        return self.payload


class FakeStreamingResponse(FakeResponse):
    async def aread(self):
        return json.dumps(self.payload).encode("utf-8")

    async def aiter_lines(self):
        for event in self.events:
            yield f"data: {json.dumps(event)}"


class FakeStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return FakeStreamingResponse(
            self.response.status_code,
            self.response.payload,
            self.response.events,
        )

    async def __aexit__(self, *_):
        return None


class FakeAsyncClient:
    response = FakeResponse()
    error = None
    request = None
    client_options = None

    def __init__(self, **kwargs):
        type(self).client_options = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def _next_response(self):
        error = type(self).error
        if isinstance(error, list):
            error = error.pop(0) if error else None
        if error:
            raise error
        if isinstance(type(self).response, list):
            return type(self).response.pop(0)
        return type(self).response

    async def post(self, url, **kwargs):
        type(self).request = (url, kwargs)
        return self._next_response()

    def stream(self, method, url, **kwargs):
        type(self).request = (url, kwargs)
        return FakeStreamContext(self._next_response())


def _set_fake_client(
    monkeypatch,
    service,
    *,
    status_code=200,
    payload=None,
    error=None,
    responses=None,
):
    FakeAsyncClient.response = (
        responses if responses is not None else FakeResponse(status_code, payload)
    )
    FakeAsyncClient.error = error
    FakeAsyncClient.request = None
    FakeAsyncClient.client_options = None
    monkeypatch.setattr(service.httpx, "AsyncClient", FakeAsyncClient)


def test_gemini_returns_valid_structured_analysis(monkeypatch):
    result_payload = {
        "is_suspicious": True,
        "detected_tactics": ["OTP/Password Request", "Urgency and Pressure"],
        "explanation": "The caller asks for a one-time code.",
        "recommended_action": "Do not share the code.",
        "confidence": 0.96,
    }
    _set_fake_client(
        monkeypatch,
        gemini_service,
        payload={
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(result_payload)}]}}
            ]
        },
    )
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")

    result = asyncio.run(gemini_service.analyze_with_gemini("Please share your OTP now."))

    assert result == result_payload
    url, request = FakeAsyncClient.request
    assert gemini_service.GEMINI_MODEL in url
    assert request["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert request["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert request["json"]["generationConfig"]["maxOutputTokens"] == 512
    assert request["params"] == {"alt": "sse"}
    assert FakeAsyncClient.client_options["timeout"].read == 60.0


def test_gemini_handles_auth_rate_limit_and_network_errors(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    for status in (401, 403, 429, 503):
        responses = (
            [FakeResponse(status_code=status), FakeResponse(status_code=status)]
            if status in gemini_service.TRANSIENT_HTTP_STATUS_CODES
            else None
        )
        _set_fake_client(
            monkeypatch, gemini_service, status_code=status, responses=responses
        )
        assert asyncio.run(gemini_service.analyze_with_gemini("test")) is None

    _set_fake_client(
        monkeypatch,
        gemini_service,
        error=httpx.ConnectError("network failure including secret"),
    )
    assert asyncio.run(gemini_service.analyze_with_gemini("test")) is None


def test_gemini_timeout_logs_error_type_without_secret(monkeypatch, caplog):
    secret = "test-gemini-key"
    monkeypatch.setattr(settings, "GEMINI_API_KEY", secret)
    _set_fake_client(
        monkeypatch,
        gemini_service,
        error=httpx.ReadTimeout(f"timeout while using {secret}"),
    )

    assert asyncio.run(gemini_service.analyze_with_gemini("test")) is None

    assert "ReadTimeout" in caplog.text
    assert secret not in caplog.text


def test_gemini_empty_read_timeout_has_actionable_log(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    _set_fake_client(
        monkeypatch,
        gemini_service,
        error=httpx.ReadTimeout(""),
    )

    assert asyncio.run(gemini_service.analyze_with_gemini("test")) is None

    assert "60-second read timeout" in caplog.text


def test_gemini_retries_one_transient_server_error(monkeypatch, caplog):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    response_text = json.dumps({
        "is_suspicious": True,
        "detected_tactics": ["OTP/Password Request"],
        "explanation": "OTP requested.",
        "recommended_action": "Do not share it.",
        "confidence": 0.9,
    })
    _set_fake_client(
        monkeypatch,
        gemini_service,
        responses=[
            FakeResponse(
                status_code=503,
                payload={"error": {
                    "status": "UNAVAILABLE",
                    "message": "Temporary service outage",
                }},
            ),
            FakeResponse(
                payload={"candidates": [{"content": {"parts": [{"text": response_text}]}}]}
            ),
        ],
    )

    result = asyncio.run(gemini_service.analyze_with_gemini("Please share your OTP."))

    assert result is not None
    assert result["is_suspicious"] is True
    assert FakeAsyncClient.response == []
    assert "UNAVAILABLE" in caplog.text
    assert "Temporary service outage" in caplog.text


def test_gemini_retries_one_transport_timeout(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    response_text = json.dumps({
        "is_suspicious": True,
        "detected_tactics": ["OTP/Password Request"],
        "explanation": "OTP requested.",
        "recommended_action": "Do not share it.",
        "confidence": 0.9,
    })
    _set_fake_client(
        monkeypatch,
        gemini_service,
        error=[httpx.ReadTimeout("provider response delayed"), None],
        payload={"candidates": [{"content": {"parts": [{"text": response_text}]}}]},
    )

    result = asyncio.run(gemini_service.analyze_with_gemini("Please share your OTP."))

    assert result is not None
    assert result["is_suspicious"] is True
    assert FakeAsyncClient.error == []


def test_gemini_joins_streamed_json_chunks(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    response_text = json.dumps({
        "is_suspicious": True,
        "detected_tactics": ["Authority Impersonation"],
        "explanation": "The caller falsely claims to be police.",
        "recommended_action": "Contact the police through an official number.",
        "confidence": 0.94,
    })
    split_at = len(response_text) // 2
    events = [
        {"candidates": [{"content": {"parts": [{"text": response_text[:split_at]}]}}]},
        {"candidates": [{"content": {"parts": [{"text": response_text[split_at:]}]}}]},
    ]
    _set_fake_client(
        monkeypatch,
        gemini_service,
        responses=[FakeResponse(events=events)],
    )

    result = asyncio.run(gemini_service.analyze_with_gemini("This is the police."))

    assert result is not None
    assert result["detected_tactics"] == ["Authority Impersonation"]


def test_gemini_rejects_malformed_structured_response(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    _set_fake_client(
        monkeypatch,
        gemini_service,
        payload={"candidates": [{"content": {"parts": [{"text": '{"confidence": 3}'}]}}]},
    )

    assert asyncio.run(gemini_service.analyze_with_gemini("test")) is None


def test_scam_analyzer_combines_gemini_with_deterministic_risk(monkeypatch):
    async def fake_gemini(_text):
        return {
            "is_suspicious": True,
            "detected_tactics": [" otp/password request ", "OTP Password Request"],
            "explanation": "A one-time code was requested.",
            "recommended_action": "Do not share the code.",
            "confidence": 0.9,
        }

    monkeypatch.setattr(scam_analyzer, "analyze_with_gemini", fake_gemini)
    result = asyncio.run(
        scam_analyzer.analyze_conversation("Please share your OTP immediately.")
    )

    assert result["ai_provider"] == "gemini"
    assert result["is_suspicious"] is True
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in {"SAFE", "CAUTION", "WARNING", "DANGER"}
    assert "OTP/Password Request" in result["detected_tactics"]
    assert len(result["detected_tactics"]) == len(set(result["detected_tactics"]))
    otp_detail = next(
        detail for detail in result["tactic_details"]
        if detail["tactic"] == "OTP/Password Request"
    )
    assert otp_detail["severity"] == "critical"


def test_gemini_fallback_detects_authority_arrest_and_otp_danger(monkeypatch):
    async def unavailable(_text):
        return None

    monkeypatch.setattr(scam_analyzer, "analyze_with_gemini", unavailable)
    text = (
        "This is the police. Share your OTP immediately or you will be arrested. "
        "Do not tell your family."
    )

    result = asyncio.run(scam_analyzer.analyze_conversation(text))

    assert result["ai_provider"] == "fallback"
    assert result["risk_score"] == 93
    assert result["risk_level"] == "DANGER"
    assert {
        "Authority Impersonation",
        "Fear and Threats",
        "Urgency and Pressure",
        "Isolation from Family/Friends",
        "OTP/Password Request",
    }.issubset(set(result["detected_tactics"]))
    assert "pattern analysis" in result["explanation"].lower()
    assert "DANGER" in result["recommended_action"]


def test_gemini_read_timeout_falls_back_to_danger_pattern_analysis(
    monkeypatch,
    caplog,
):
    secret = "test-gemini-key"
    monkeypatch.setattr(settings, "GEMINI_API_KEY", secret)
    _set_fake_client(
        monkeypatch,
        gemini_service,
        error=httpx.ReadTimeout("provider took too long"),
    )
    text = (
        "This is the police. Share your OTP immediately or you will be arrested. "
        "Do not tell your family."
    )

    result = asyncio.run(scam_analyzer.analyze_conversation(text))

    assert result["ai_provider"] == "fallback"
    assert result["risk_score"] == 93
    assert result["risk_level"] == "DANGER"
    assert "Authority Impersonation" in result["detected_tactics"]
    assert "OTP/Password Request" in result["detected_tactics"]
    assert "DANGER" in result["recommended_action"]
    assert secret not in caplog.text


def test_gemini_read_timeout_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(settings, "GEMINI_READ_TIMEOUT_SECONDS", 60.0)
    response_text = json.dumps({
        "is_suspicious": False,
        "detected_tactics": [],
        "explanation": "No scam tactics found.",
        "recommended_action": "Remain cautious.",
        "confidence": 0.8,
    })
    _set_fake_client(
        monkeypatch,
        gemini_service,
        payload={"candidates": [{"content": {"parts": [{"text": response_text}]}}]},
    )

    asyncio.run(gemini_service.analyze_with_gemini("Harmless sample text."))

    assert FakeAsyncClient.client_options["timeout"].read == 60.0


def test_tactic_merge_normalizes_names_and_keeps_highest_severity():
    merged = scam_analyzer.merge_tactic_details([
        {
            "tactic": " Custom  Signal ",
            "severity": "high",
            "evidence": "Pattern evidence.",
        },
        {
            "tactic": "custom-signal",
            "severity": "critical",
            "evidence": "Gemini evidence.",
        },
    ])

    assert len(merged) == 1
    assert merged[0]["tactic"] == "Custom Signal"
    assert merged[0]["severity"] == "critical"
    assert "Pattern evidence." in merged[0]["evidence"]
    assert "Gemini evidence." in merged[0]["evidence"]


def test_ai_and_deterministic_tactics_have_consistent_deduplicated_score():
    text = "Please share your OTP immediately."
    deterministic_score, _, deterministic_tactics = analyze_text_deterministic(text)

    score, level, tactics = combine_scores(
        ai_score=98,
        deterministic_score=deterministic_score,
        ai_tactics=[" otp/password request ", "OTP Password Request"],
        det_tactics=deterministic_tactics,
    )

    assert set(tactics) == {"OTP/Password Request", "Urgency and Pressure"}
    assert score == 98
    assert score >= deterministic_score
    assert level == "DANGER"


def test_high_confidence_ai_scam_tactic_raises_risk_score():
    score, level, tactics = combine_scores(
        ai_score=92,
        deterministic_score=0,
        ai_tactics=["OTP request"],
        det_tactics=[],
    )

    assert tactics == ["OTP/Password Request"]
    assert score == 92
    assert level == "DANGER"


def test_generic_ai_suspicion_without_tactic_stays_capped_at_caution():
    score, level, tactics = combine_scores(
        ai_score=96,
        deterministic_score=0,
        ai_tactics=[],
        det_tactics=[],
    )

    assert tactics == []
    assert score == 30
    assert level == "CAUTION"


def test_sarvam_transcribes_tamil_and_english_using_current_endpoint(monkeypatch, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"sample audio")
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "test-sarvam-key")
    for language in ("ta-IN", "en-IN"):
        _set_fake_client(
            monkeypatch,
            sarvam_service,
            payload={"transcript": "sample transcript", "language_code": language},
        )

        result = asyncio.run(sarvam_service.transcribe_audio(str(audio), language))

        assert result == {
            "transcript": "sample transcript",
            "language_detected": language,
            "provider": "sarvam",
        }
        url, request = FakeAsyncClient.request
        assert url == "https://api.sarvam.ai/speech-to-text"
        assert request["data"] == {"model": "saaras:v4", "language_code": language}
        assert request["headers"]["api-subscription-key"] == "test-sarvam-key"


def test_sarvam_handles_auth_rate_limit_and_network_errors(monkeypatch, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"sample audio")
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "test-sarvam-key")

    for status, expected in (
        (401, "authentication failed"),
        (403, "authentication failed"),
        (429, "rate limit"),
        (503, "temporarily unavailable"),
    ):
        _set_fake_client(monkeypatch, sarvam_service, status_code=status)
        result = asyncio.run(sarvam_service.transcribe_audio(str(audio), "en-IN"))
        assert expected in result["error"]

    _set_fake_client(
        monkeypatch,
        sarvam_service,
        error=httpx.ConnectError("network failure including secret"),
    )
    result = asyncio.run(sarvam_service.transcribe_audio(str(audio), "en-IN"))
    assert "network error" in result["error"]
    assert "secret" not in result["error"]


def test_sarvam_rejects_unsupported_language_without_request(monkeypatch, tmp_path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"sample audio")
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "test-sarvam-key")
    _set_fake_client(monkeypatch, sarvam_service)

    result = asyncio.run(sarvam_service.transcribe_audio(str(audio), "fr-FR"))

    assert "Unsupported language" in result["error"]
    assert FakeAsyncClient.request is None
