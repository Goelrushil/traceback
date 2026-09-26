"""TRACEBACK claim validation and health engine."""

from dataclasses import dataclass, field
import re

from traceback_core.ai.schemas import Claim


CLAIM_HEALTH_SUPPORTED = "SUPPORTED"
CLAIM_HEALTH_INFERRED = "INFERRED"
CLAIM_HEALTH_WEAK = "WEAK"
CLAIM_HEALTH_UNSUPPORTED = "UNSUPPORTED"


@dataclass
class ClaimAssessment:
    """Deterministic assessment of a single AI-generated claim."""

    claim_id: str
    claim_text: str
    claim_type: str
    evidence_ids: list[str] = field(default_factory=list)

    health: str = CLAIM_HEALTH_UNSUPPORTED
    evidence_valid: bool = False
    inflation_detected: bool = False

    reason: str = ""
    suggested_rewrite: str | None = None


def _normalize(text: str) -> str:
    """Normalize text for lightweight deterministic comparisons."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _evidence_supports_claim(
    claim_text: str,
    evidence_texts: list[str],
) -> bool:
    """
    Conservative lexical support check.

    This is intentionally deterministic. It does not claim semantic
    understanding; it checks whether important claim terms are present
    across the cited evidence.
    """
    claim = _normalize(claim_text)

    # Strong comparative language requires explicit evidence.
    strong_terms = {
        "safest",
        "best",
        "strongest",
        "most reliable",
        "lowest",
        "highest",
        "worst",
        "fastest",
        "slowest",
    }

    for term in strong_terms:
        if term in claim:
            combined = " ".join(_normalize(item) for item in evidence_texts)
            if term in combined:
                return True

            # "safest" should not be considered supported merely because
            # the evidence says "lowest incident rate".
            return False

    # For ordinary factual claims, compare meaningful words.
    stop_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "is",
        "was",
        "were",
        "has",
        "had",
        "have",
        "to",
        "of",
        "in",
        "on",
        "for",
        "during",
        "among",
        "both",
        "that",
        "this",
        "with",
        "from",
    }

    claim_words = {
        word
        for word in re.findall(r"[a-z0-9]+", claim)
        if len(word) > 2 and word not in stop_words
    }

    evidence_words = {
        word
        for text in evidence_texts
        for word in re.findall(r"[a-z0-9]+", _normalize(text))
        if len(word) > 2 and word not in stop_words
    }

    if not claim_words:
        return False

    overlap = len(claim_words & evidence_words) / len(claim_words)

    return overlap >= 0.5


def _detect_inflation(
    claim_text: str,
    evidence_texts: list[str],
) -> tuple[bool, str | None]:
    """
    Detect common cases where AI wording becomes stronger than evidence.
    """

    claim = _normalize(claim_text)
    evidence = _normalize(" ".join(evidence_texts))

    inflation_patterns = [
        (
            "safest",
            "lowest observed incident rate",
            "The evidence supports the narrower statement about the lowest observed incident rate, not the broader claim that the vendor is the safest.",
        ),
        (
            "strongest compliance performance",
            "compliance documentation",
            "The evidence confirms compliance documentation was submitted, but does not establish strongest compliance performance.",
        ),
        (
            "best vendor",
            "lowest observed incident rate",
            "The evidence supports the incident-rate comparison but does not establish that the vendor is the best overall choice.",
        ),
        (
            "most reliable",
            "lowest observed incident rate",
            "The evidence does not establish overall reliability from incident rate alone.",
        ),
    ]

    for inflated_phrase, supported_phrase, reason in inflation_patterns:
        if inflated_phrase in claim and supported_phrase in evidence:
            return True, reason

    return False, None


def assess_claim(
    claim: Claim,
    evidence_by_id: dict[str, str],
) -> ClaimAssessment:
    """Assess one AI-generated claim against available evidence."""

    assessment = ClaimAssessment(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        claim_type=claim.claim_type,
        evidence_ids=list(claim.evidence_ids),
    )

    # 1. Validate evidence references.
    missing_ids = [
        evidence_id
        for evidence_id in claim.evidence_ids
        if evidence_id not in evidence_by_id
    ]

    if missing_ids:
        assessment.health = CLAIM_HEALTH_UNSUPPORTED
        assessment.reason = (
            f"Claim references evidence that does not exist: "
            f"{', '.join(missing_ids)}."
        )
        return assessment

    if not claim.evidence_ids:
        assessment.health = CLAIM_HEALTH_UNSUPPORTED
        assessment.reason = "Claim has no supporting evidence references."
        return assessment

    assessment.evidence_valid = True

    cited_evidence = [
        evidence_by_id[evidence_id]
        for evidence_id in claim.evidence_ids
    ]

    # 2. Detect wording inflation.
    inflation, inflation_reason = _detect_inflation(
        claim.text,
        cited_evidence,
    )

    assessment.inflation_detected = inflation

    if inflation:
        assessment.health = CLAIM_HEALTH_WEAK
        assessment.reason = inflation_reason or "Claim wording exceeds evidence."

        # Prefer the strongest explicit evidence sentence as a correction.
        assessment.suggested_rewrite = max(
            cited_evidence,
            key=lambda text: len(text),
        )

        return assessment

    # 3. Determine basic support.
    supported = _evidence_supports_claim(
        claim.text,
        cited_evidence,
    )

    if supported:
        if claim.claim_type in {"inference", "conclusion"}:
            assessment.health = CLAIM_HEALTH_INFERRED
            assessment.reason = (
                "The cited evidence supports the claim as an inference, "
                "but the wording is not a direct statement of the evidence."
            )
        else:
            assessment.health = CLAIM_HEALTH_SUPPORTED
            assessment.reason = "Claim is supported by the cited evidence."
    else:
        assessment.health = CLAIM_HEALTH_WEAK
        assessment.reason = (
            "The cited evidence is related to the claim, but does not "
            "provide sufficient direct support for the wording."
        )

    return assessment


def assess_claims(
    claims: list[Claim],
    evidence_by_id: dict[str, str],
) -> list[ClaimAssessment]:
    """Assess all claims produced by the AI."""
    return [
        assess_claim(claim, evidence_by_id)
        for claim in claims
    ]