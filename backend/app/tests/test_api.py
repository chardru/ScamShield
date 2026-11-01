"""
ScamShield Backend - Test Suite.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import init_db
from app.services.risk_engine import (
    analyze_text_deterministic,
    get_risk_level,
    combine_scores,
    generate_recommendation,
)

# Initialize DB tables before tests (TestClient doesn't fire startup events)
init_db()

client = TestClient(app)


# ── Health & Root ──────────────────────────────────────────────

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "ScamShield" in data["message"]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data


# ── Risk Engine ────────────────────────────────────────────────

def test_risk_level_safe():
    assert get_risk_level(0) == "SAFE"
    assert get_risk_level(29) == "SAFE"


def test_risk_level_caution():
    assert get_risk_level(30) == "CAUTION"
    assert get_risk_level(59) == "CAUTION"


def test_risk_level_warning():
    assert get_risk_level(60) == "WARNING"
    assert get_risk_level(79) == "WARNING"


def test_risk_level_danger():
    assert get_risk_level(80) == "DANGER"
    assert get_risk_level(100) == "DANGER"


def test_safe_conversation():
    text = "Hi, how are you? Let's meet for coffee tomorrow at 3pm."
    score, level, tactics = analyze_text_deterministic(text)
    assert score < 30
    assert level == "SAFE"
    assert len(tactics) == 0


def test_otp_request_detection():
    text = "Please share the OTP you received on your phone to verify your account."
    score, level, tactics = analyze_text_deterministic(text)
    assert score >= 25
    tactic_names = [t.tactic for t in tactics]
    assert "OTP/Password Request" in tactic_names


def test_authority_impersonation_detection():
    text = "This is Inspector Kumar from CBI. You must verify your identity immediately or face arrest."
    score, level, tactics = analyze_text_deterministic(text)
    assert score >= 30
    tactic_names = [t.tactic for t in tactics]
    assert any("Authority" in t or "Fear" in t for t in tactic_names)


def test_money_transfer_detection():
    text = "Transfer the money to this safe government account via NEFT immediately. This is urgent."
    score, level, tactics = analyze_text_deterministic(text)
    assert score >= 25
    tactic_names = [t.tactic for t in tactics]
    assert "Suspicious Money Transfer" in tactic_names


def test_digital_arrest_detection():
    text = "You are under digital arrest. Stay on this video call. Do not disconnect or the police will come."
    score, level, tactics = analyze_text_deterministic(text)
    assert score >= 25
    tactic_names = [t.tactic for t in tactics]
    assert "Digital Arrest Threat" in tactic_names


def test_empty_text():
    score, level, tactics = analyze_text_deterministic("")
    assert score == 0
    assert level == "SAFE"
    assert len(tactics) == 0


def test_score_boundaries():
    """Risk score must always be 0-100."""
    long_scam = (
        "This is the CBI Inspector. You are under digital arrest. "
        "Share your OTP and bank account number immediately. "
        "Transfer Rs 50000 via UPI to our safe account. "
        "Install AnyDesk on your phone. Don't tell anyone. "
        "You will be arrested if you don't comply within 30 minutes."
    )
    score, level, tactics = analyze_text_deterministic(long_scam)
    assert 0 <= score <= 100


def test_recommendation_safe():
    rec = generate_recommendation("SAFE", [])
    assert "No immediate concerns" in rec


def test_recommendation_danger():
    rec = generate_recommendation("DANGER", ["Digital Arrest Threat"])
    assert "DANGER" in rec
    assert "digital arrest" in rec.lower()


# ── API Analysis ───────────────────────────────────────────────

def test_analyze_endpoint_safe():
    response = client.post("/api/analyze", json={
        "text": "Hey! Are we still on for the movie tonight?",
    })
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert data["risk_level"] == "SAFE"


def test_analyze_endpoint_suspicious():
    response = client.post("/api/analyze", json={
        "text": "This is the police. Share your OTP and transfer money to this account immediately.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] >= 30
    assert data["is_suspicious"] is True
    assert len(data["detected_tactics"]) > 0
    assert data["tactic_details"]
    assert all(detail["tactic"] in data["detected_tactics"] for detail in data["tactic_details"])


def test_analyze_empty_text():
    response = client.post("/api/analyze", json={"text": ""})
    assert response.status_code == 422  # Validation error


# ── Reports ────────────────────────────────────────────────────

def test_reports_list():
    response = client.get("/api/reports")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert "total" in data


def test_report_not_found():
    response = client.get("/api/reports/nonexistent_id")
    assert response.status_code == 404


def test_report_create_and_retrieve():
    # Create via analysis
    create_resp = client.post("/api/analyze", json={
        "text": "Hello friend, let's go for lunch.",
    })
    assert create_resp.status_code == 200
    report_id = create_resp.json()["report_id"]

    # Retrieve
    get_resp = client.get(f"/api/reports/{report_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == report_id


def test_report_delete():
    # Create
    create_resp = client.post("/api/analyze", json={
        "text": "Test conversation for deletion.",
    })
    report_id = create_resp.json()["report_id"]

    # Delete
    del_resp = client.delete(f"/api/reports/{report_id}")
    assert del_resp.status_code == 200

    # Verify deleted
    get_resp = client.get(f"/api/reports/{report_id}")
    assert get_resp.status_code == 404


# ── Demo Conversations ────────────────────────────────────────

def test_demo_conversations():
    response = client.get("/api/demo-conversations")
    assert response.status_code == 200
    data = response.json()
    assert "conversations" in data
    assert len(data["conversations"]) >= 4


# ── Notification Status ───────────────────────────────────────

def test_notification_status():
    response = client.get("/api/notifications/status")
    assert response.status_code == 200
    data = response.json()
    assert "telegram" in data


# ── Transcription Status ──────────────────────────────────────

def test_transcription_status():
    response = client.get("/api/transcription-status")
    assert response.status_code == 200
    data = response.json()
    assert "supported_formats" in data
