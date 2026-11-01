"""
ScamShield Backend - Scam Analyzer.

Orchestrates AI analysis + deterministic risk engine to produce final results.
Includes demo mode with sample conversations.
"""

import logging
from typing import Dict, Any
from app.services.gemini_service import analyze_with_gemini, get_fallback_analysis
from app.services.risk_engine import (
    TACTIC_DEFINITIONS,
    TACTIC_SEVERITY_RANK,
    analyze_text_deterministic,
    canonicalize_tactic_name,
    combine_scores,
    generate_recommendation,
    normalize_tactic_name,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# Demo conversations for testing without API keys
DEMO_CONVERSATIONS = {
    "safe_normal": {
        "text": "Hi, how are you? I wanted to check if we're still meeting for lunch tomorrow at the usual place. Let me know!",
        "label": "Safe - Normal Conversation",
    },
    "suspicious_authority": {
        "text": (
            "This is Inspector Sharma from Delhi Police Cyber Cell. "
            "Your Aadhaar number has been linked to illegal transactions. "
            "You must verify your identity immediately or face arrest. "
            "Share your bank account details for verification. "
            "Do not tell anyone about this call — it is confidential."
        ),
        "label": "Suspicious - Authority Impersonation",
    },
    "digital_arrest": {
        "text": (
            "This is the CBI. A parcel in your name has been seized at Mumbai customs "
            "containing illegal drugs. You are under digital arrest. "
            "Stay on this video call. Do not disconnect. Do not contact anyone. "
            "You must transfer Rs 50,000 to this government safe account immediately "
            "or a physical arrest warrant will be issued within 2 hours."
        ),
        "label": "Danger - Digital Arrest Scam",
    },
    "otp_request": {
        "text": (
            "Hello, this is your bank's fraud department. We detected suspicious activity "
            "on your account. To secure your account, please share the OTP you just received "
            "on your phone. Also, we need your credit card number and CVV for verification."
        ),
        "label": "Danger - OTP/Bank Details Request",
    },
    "money_transfer": {
        "text": (
            "Congratulations! You have won the international lottery worth $5,000,000. "
            "To claim your prize, you must pay a processing fee of Rs 25,000 via UPI "
            "to this number immediately. This offer expires in 30 minutes. "
            "Send the money via GPay or PhonePe right now. Hurry, don't miss this!"
        ),
        "label": "Danger - Money Transfer Scam",
    },
}


def merge_tactic_details(details: list[Dict[str, str]]) -> list[Dict[str, str]]:
    """Merge tactic details by normalized name, preserving maximum severity."""
    merged: Dict[str, Dict[str, str]] = {}
    for detail in details:
        canonical_name = canonicalize_tactic_name(detail["tactic"])
        key = normalize_tactic_name(canonical_name)
        severity = detail.get("severity", "medium").casefold()
        if severity not in TACTIC_SEVERITY_RANK:
            severity = "medium"
        evidence = detail.get("evidence", "").strip()

        existing = merged.get(key)
        if existing is None:
            merged[key] = {
                "tactic": canonical_name,
                "severity": severity,
                "evidence": evidence,
            }
            continue

        if TACTIC_SEVERITY_RANK[severity] > TACTIC_SEVERITY_RANK[existing["severity"]]:
            existing["severity"] = severity
        if evidence and evidence not in existing["evidence"]:
            existing["evidence"] = (
                f"{existing['evidence']} {evidence}".strip()
            )
    return list(merged.values())


async def analyze_conversation(text: str, source: str = "text_input") -> Dict[str, Any]:
    """
    Perform full scam analysis on conversation text.
    
    Combines AI analysis (Gemini) with deterministic risk scoring.
    Falls back gracefully when AI is unavailable.
    """
    # Step 1: Deterministic analysis (always runs)
    det_score, det_level, det_tactics = analyze_text_deterministic(text)
    deterministic_details = {tactic.tactic: tactic for tactic in det_tactics}

    # Step 2: AI analysis (may be unavailable)
    ai_result = await analyze_with_gemini(text)
    ai_provider = "demo"

    if ai_result is not None:
        ai_provider = "gemini"
        ai_score = int(ai_result.get("confidence", 0.0) * 100) if ai_result.get("is_suspicious") else 0
        ai_tactics = ai_result.get("detected_tactics", [])
        ai_confidence = ai_result.get("confidence", 0.0)

        # Combine AI + deterministic
        final_score, final_level, all_tactics = combine_scores(
            ai_score, det_score, ai_tactics, det_tactics
        )

        explanation = ai_result.get("explanation", "")
        if not explanation:
            explanation = f"Analysis detected {len(all_tactics)} potential scam indicator(s)."
    else:
        # Fallback — deterministic only
        fallback = get_fallback_analysis()
        ai_provider = fallback.get("ai_provider", "fallback")
        final_score = det_score
        final_level = det_level
        all_tactics = [t.tactic for t in det_tactics]
        explanation = fallback["explanation"]
        if det_tactics:
            explanation += f" Pattern analysis detected {len(det_tactics)} indicator(s): {', '.join(all_tactics)}."

    # Preserve evidence from deterministic matches and include Gemini-only findings.
    tactic_definition_by_name = {
        definition["name"]: definition
        for definition in TACTIC_DEFINITIONS.values()
    }
    tactic_detail_candidates = []
    for tactic_name in all_tactics:
        canonical_name = canonicalize_tactic_name(tactic_name)
        deterministic_match = deterministic_details.get(canonical_name)
        if deterministic_match:
            tactic_detail_candidates.append({
                "tactic": canonical_name,
                "severity": deterministic_match.severity,
                "evidence": deterministic_match.evidence,
            })
            continue

        definition = tactic_definition_by_name.get(canonical_name)
        tactic_detail_candidates.append({
            "tactic": canonical_name,
            "severity": definition["severity"] if definition else "medium",
            "evidence": "Identified by Gemini AI analysis.",
        })
    tactic_details = merge_tactic_details(tactic_detail_candidates)
    all_tactics = [detail["tactic"] for detail in tactic_details]

    # Rebuild recommendation after canonicalization so its tactic-specific advice applies.
    recommendation = generate_recommendation(final_level, all_tactics)

    # Compute confidence
    if ai_result:
        confidence = ai_result.get("confidence", 0.0)
    elif det_tactics:
        # Deterministic confidence based on number and severity of matches
        confidence = min(0.8, len(det_tactics) * 0.2)
    else:
        confidence = 0.1

    return {
        "is_suspicious": final_score >= 30,
        "risk_score": final_score,
        "risk_level": final_level,
        "detected_tactics": all_tactics,
        "tactic_details": tactic_details,
        "explanation": explanation,
        "recommended_action": recommendation,
        "confidence": round(confidence, 2),
        "ai_provider": ai_provider,
        "source": source,
    }


def get_demo_conversations():
    """Return demo conversation samples."""
    return [
        {"id": key, "text": val["text"], "label": val["label"]}
        for key, val in DEMO_CONVERSATIONS.items()
    ]
