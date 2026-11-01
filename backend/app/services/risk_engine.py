"""
ScamShield Backend - Deterministic Risk Engine.

Calculates risk scores using weighted tactic scoring.
This module works independently of any AI provider.

Risk Levels:
  0-29:  SAFE
  30-59: CAUTION
  60-79: WARNING
  80-100: DANGER

Scoring Weights (documented):
  - Authority impersonation: 20 points
  - Fear and threats: 18 points
  - Urgency and pressure: 15 points
  - Isolation from family/friends: 15 points
  - OTP/password requests: 25 points
  - Bank details requests: 25 points
  - Suspicious money transfer: 25 points
  - Remote access app requests: 22 points
  - Digital arrest threats: 25 points
  - Suspicious payment links: 18 points
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class TacticMatch:
    """A matched scam tactic with metadata."""
    tactic: str
    severity: str  # low, medium, high, critical
    weight: int
    evidence: str
    matched_patterns: List[str]


# Tactic definitions with keywords, weight, and severity
TACTIC_DEFINITIONS: Dict[str, dict] = {
    "authority_impersonation": {
        "name": "Authority Impersonation",
        "weight": 20,
        "severity": "high",
        "patterns": [
            r"\b(police|officer|inspector|superintendent|commissioner)\b",
            r"\b(cbi|cia|fbi|interpol|customs|narcotics|enforcement)\b",
            r"\b(rbi|reserve bank|sebi|income tax|tax department)\b",
            r"\b(government|ministry|magistrate|court order|warrant)\b",
            r"\b(i am calling from|this is .{0,20} department)\b",
            r"\b(official notice|legal action|federal agent)\b",
        ],
        "context_required": [
            r"\b(verify|confirm|immediate(?:ly)?|comply|cooperate|legal)\b",
        ],
    },
    "fear_and_threats": {
        "name": "Fear and Threats",
        "weight": 18,
        "severity": "high",
        "patterns": [
            r"\b(arrest(?:ed)?|jail|prison|imprison|detained|custody)\b",
            r"\b(lawsuit|prosecution|penalty|fine|punishment)\b",
            r"\b(cancel|suspend|block|freeze|seize).{0,20}(account|card|passport|license)\b",
            r"\b(criminal|illegal|fraud|money laundering)\b",
            r"\b(threatening|consequences|serious trouble)\b",
        ],
        "context_required": [
            r"\b(you|your|account|immediately)\b",
        ],
    },
    "urgency_and_pressure": {
        "name": "Urgency and Pressure",
        "weight": 15,
        "severity": "medium",
        "patterns": [
            r"\b(immediately|right now|urgent|emergency)\b",
            r"\b(last chance|final warning|deadline|expires)\b",
            r"\b(hurry|quickly|fast|asap|within .{0,10} (hour|minute))\b",
            r"\b(don'?t delay|act now|time is running out)\b",
            r"\b(limited time|offer expires|today only)\b",
        ],
        "context_required": [],
    },
    "isolation_tactics": {
        "name": "Isolation from Family/Friends",
        "weight": 15,
        "severity": "high",
        "patterns": [
            r"\b(don'?t tell|do not tell|don'?t share|do not share)\b",
            r"\b(keep.{0,10}secret|confidential|between us)\b",
            r"\b(don'?t inform|do not inform|don'?t discuss|do not discuss)\b",
            r"\b(alone|private|secretly|no one should know)\b",
            r"\b(don'?t call|do not contact).{0,20}(police|family|friend|anyone)\b",
        ],
        "context_required": [],
    },
    "otp_password_request": {
        "name": "OTP/Password Request",
        "weight": 25,
        "severity": "critical",
        "patterns": [
            r"\b(otp|one.?time.?password|verification code)\b",
            r"\b(share|send|tell|give).{0,20}(otp|password|pin|code)\b",
            r"\b(password|pin|passcode|security code)\b",
            r"\b(cvv|card number|expiry date|security question)\b",
        ],
        "context_required": [
            r"\b(share|send|provide|give|tell|enter|verify)\b",
        ],
    },
    "bank_details_request": {
        "name": "Bank Details Request",
        "weight": 25,
        "severity": "critical",
        "patterns": [
            r"\b(bank account|account number|ifsc|routing number)\b",
            r"\b(credit card|debit card|card details|card number)\b",
            r"\b(net banking|internet banking|login credentials)\b",
            r"\b(aadhaar|aadhar|pan card|social security)\b",
        ],
        "context_required": [
            r"\b(share|send|provide|give|verify|update|confirm)\b",
        ],
    },
    "money_transfer_request": {
        "name": "Suspicious Money Transfer",
        "weight": 25,
        "severity": "critical",
        "patterns": [
            r"\b(transfer|send|deposit|wire).{0,20}(money|amount|funds|payment)\b",
            r"\b(upi|gpay|phonepe|paytm|neft|rtgs|imps)\b",
            r"\b(gift card|bitcoin|crypto|western union)\b",
            r"\b(safe account|rbi account|government account|escrow)\b",
            r"\b(refundable deposit|security deposit|processing fee)\b",
        ],
        "context_required": [],
    },
    "remote_access_request": {
        "name": "Remote Access App Request",
        "weight": 22,
        "severity": "critical",
        "patterns": [
            r"\b(anydesk|teamviewer|quick support|remote desktop)\b",
            r"\b(screen share|screen sharing|share your screen)\b",
            r"\b(install|download).{0,20}(app|application|software)\b",
            r"\b(remote access|control your device|take control)\b",
        ],
        "context_required": [],
    },
    "digital_arrest": {
        "name": "Digital Arrest Threat",
        "weight": 25,
        "severity": "critical",
        "patterns": [
            r"\b(digital arrest|cyber arrest|online arrest)\b",
            r"\b(video call|stay on.{0,10}(call|camera|video))\b",
            r"\b(don'?t disconnect|do not disconnect|stay.{0,10}(online|connected))\b",
            r"\b(under surveillance|monitoring|being watched)\b",
        ],
        "context_required": [
            r"\b(arrest|police|officer|legal|court)\b",
        ],
    },
    "suspicious_links": {
        "name": "Suspicious Payment Links",
        "weight": 18,
        "severity": "high",
        "patterns": [
            r"(https?://[^\s]+\.(xyz|tk|ml|ga|cf|pw|click|top|buzz))",
            r"\b(click.{0,10}(link|here|below)|open.{0,10}link)\b",
            r"\b(payment link|pay here|scan.{0,10}(qr|code))\b",
            r"\b(bit\.ly|tinyurl|short\.url|t\.co)\b",
        ],
        "context_required": [],
    },
}

TACTIC_SEVERITY_RANK = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

_TACTIC_DEFINITION_BY_NORMALIZED_NAME = {
    re.sub(r"[^a-z0-9]+", "", definition["name"].casefold()): definition
    for definition in TACTIC_DEFINITIONS.values()
}
_TACTIC_ALIASES = {
    "fearthreats": "Fear and Threats",
    "threatsfear": "Fear and Threats",
    "urgency": "Urgency and Pressure",
    "isolation": "Isolation from Family/Friends",
    "otprequest": "OTP/Password Request",
    "otp": "OTP/Password Request",
    "bankingdetailsrequest": "Bank Details Request",
    "moneytransfer": "Suspicious Money Transfer",
    "moneytransferdemand": "Suspicious Money Transfer",
    "remoteaccess": "Remote Access App Request",
    "digitalarrestthreat": "Digital Arrest Threat",
}


def normalize_tactic_name(name: str) -> str:
    """Return a punctuation- and case-insensitive key for a tactic name."""
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def canonicalize_tactic_name(name: str) -> str:
    """Map recognized tactic variants to the canonical display name."""
    normalized_name = normalize_tactic_name(name)
    if normalized_name in _TACTIC_ALIASES:
        return _TACTIC_ALIASES[normalized_name]
    definition = _TACTIC_DEFINITION_BY_NORMALIZED_NAME.get(normalized_name)
    return definition["name"] if definition else " ".join(name.split())


def score_tactics(tactic_names: List[str]) -> int:
    """Score each recognized tactic once using the deterministic tactic weights."""
    unique_definitions = {}
    for name in tactic_names:
        canonical_name = canonicalize_tactic_name(name)
        normalized_name = normalize_tactic_name(canonical_name)
        definition = _TACTIC_DEFINITION_BY_NORMALIZED_NAME.get(normalized_name)
        if definition:
            unique_definitions[normalized_name] = definition

    raw_score = sum(definition["weight"] for definition in unique_definitions.values())
    if len(unique_definitions) > 5:
        raw_score = int(raw_score * 0.85)
    return min(100, max(0, raw_score))


def get_risk_level(score: int) -> str:
    """Convert risk score to risk level."""
    if score >= 80:
        return "DANGER"
    elif score >= 60:
        return "WARNING"
    elif score >= 30:
        return "CAUTION"
    else:
        return "SAFE"


def analyze_text_deterministic(text: str) -> Tuple[int, str, List[TacticMatch]]:
    """
    Analyze conversation text using pattern matching and weighted scoring.
    
    Returns:
        Tuple of (risk_score, risk_level, list_of_matched_tactics)
    """
    if not text or not text.strip():
        return 0, "SAFE", []

    text_lower = text.lower()
    matched_tactics: List[TacticMatch] = []
    seen_tactic_names = set()

    for tactic_id, tactic_def in TACTIC_DEFINITIONS.items():
        pattern_matches = []
        
        # Check main patterns
        for pattern in tactic_def["patterns"]:
            found = re.findall(pattern, text_lower, re.IGNORECASE)
            if found:
                pattern_matches.extend([str(f) for f in found])

        if not pattern_matches:
            continue

        # Check context requirements (if any pattern must also match)
        context_patterns = tactic_def.get("context_required", [])
        if context_patterns:
            context_found = False
            for ctx_pattern in context_patterns:
                if re.search(ctx_pattern, text_lower, re.IGNORECASE):
                    context_found = True
                    break
            if not context_found:
                continue

        # Avoid double-counting the same tactic
        tactic_name = tactic_def["name"]
        if tactic_name in seen_tactic_names:
            continue
        seen_tactic_names.add(tactic_name)

        matched_tactics.append(TacticMatch(
            tactic=tactic_name,
            severity=tactic_def["severity"],
            weight=tactic_def["weight"],
            evidence=f"Detected patterns: {', '.join(pattern_matches[:3])}",
            matched_patterns=pattern_matches[:5],
        ))

    risk_score = score_tactics([tactic.tactic for tactic in matched_tactics])
    risk_level = get_risk_level(risk_score)

    return risk_score, risk_level, matched_tactics


def combine_scores(
    ai_score: Optional[int],
    deterministic_score: int,
    ai_tactics: List[str],
    det_tactics: List[TacticMatch],
) -> Tuple[int, str, List[str]]:
    """
    Combine AI analysis with deterministic scoring.
    
    Scores the canonical union of detected tactics with deterministic weights.
    A generic AI suspicion with no recognized tactic evidence is capped at
    CAUTION. High-confidence AI findings with recognized tactics retain the
    model confidence score, while deterministic evidence remains the baseline.
    """
    all_tactics = []
    seen_tactics = set()
    for tactic_name in [t.tactic for t in det_tactics] + ai_tactics:
        canonical_name = canonicalize_tactic_name(tactic_name)
        normalized_name = normalize_tactic_name(canonical_name)
        if normalized_name and normalized_name not in seen_tactics:
            all_tactics.append(canonical_name)
            seen_tactics.add(normalized_name)

    merged_score = score_tactics(all_tactics)
    if merged_score == 0 and ai_score:
        merged_score = 30
    elif ai_score is not None and ai_score >= 80 and score_tactics(ai_tactics) > 0:
        merged_score = max(merged_score, ai_score)
    merged_score = max(deterministic_score, merged_score)
    return merged_score, get_risk_level(merged_score), all_tactics


def generate_recommendation(risk_level: str, tactics: List[str]) -> str:
    """Generate safety recommendations based on risk level and detected tactics."""
    if risk_level == "SAFE":
        return "No immediate concerns detected. Stay vigilant and never share sensitive information with unknown callers."

    if risk_level == "CAUTION":
        return (
            "Some suspicious indicators detected. Be alert. "
            "Do not share personal or financial information. "
            "Verify the caller's identity through official channels."
        )

    if risk_level == "WARNING":
        recs = [
            "Warning: Multiple suspicious indicators detected.",
            "Do NOT share OTPs, passwords, or banking details.",
            "Verify the caller's identity through official channels.",
        ]
        if "Remote Access App Request" in tactics:
            recs.append("Do NOT install AnyDesk, TeamViewer, or similar remote access apps.")
        if "Isolation from Family/Friends" in tactics:
            recs.append("Talk to a trusted family member or friend about this call.")
        return " ".join(recs)

    # DANGER
    recs = [
        "DANGER: High-risk scam indicators detected!",
        "Stop the conversation immediately.",
        "Do NOT share OTPs, passwords, or banking details.",
        "Do NOT transfer money to any account.",
        "Contact the relevant organisation through its official website or number.",
        "Report this incident to cybercrime helpline 1930 (India) or local authorities.",
    ]
    if "Digital Arrest Threat" in tactics:
        recs.append("'Digital arrest' is NOT a real legal procedure — this is a scam.")
    return " ".join(recs)
