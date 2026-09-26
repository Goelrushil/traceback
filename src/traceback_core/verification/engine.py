"""TRACEBACK deterministic verification engine."""

from dataclasses import dataclass, field

from traceback_core.claims.engine import (
    CLAIM_HEALTH_INFERRED,
    CLAIM_HEALTH_SUPPORTED,
    CLAIM_HEALTH_UNSUPPORTED,
    CLAIM_HEALTH_WEAK,
    ClaimAssessment,
    assess_claims,
)
from traceback_core.ai.schemas import Claim


VERIFICATION_PASSED = "PASSED"
VERIFICATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
VERIFICATION_FAILED = "FAILED"


@dataclass
class VerificationResult:
    """Aggregate verification result for an investigation."""

    status: str
    total_claims: int
    supported_claims: int
    inferred_claims: int
    weak_claims: int
    unsupported_claims: int

    evidence_coverage: float
    inflation_count: int

    assessments: list[ClaimAssessment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def verify_claims(
    claims: list[Claim],
    evidence_by_id: dict[str, str],
) -> VerificationResult:
    """
    Verify all AI-generated claims against the supplied evidence.

    This layer is deterministic and independent from the generating model.
    """

    assessments = assess_claims(
        claims=claims,
        evidence_by_id=evidence_by_id,
    )

    total_claims = len(assessments)

    supported_claims = sum(
        assessment.health == CLAIM_HEALTH_SUPPORTED
        for assessment in assessments
    )

    inferred_claims = sum(
        assessment.health == CLAIM_HEALTH_INFERRED
        for assessment in assessments
    )

    weak_claims = sum(
        assessment.health == CLAIM_HEALTH_WEAK
        for assessment in assessments
    )

    unsupported_claims = sum(
        assessment.health == CLAIM_HEALTH_UNSUPPORTED
        for assessment in assessments
    )

    inflation_count = sum(
        assessment.inflation_detected
        for assessment in assessments
    )

    # Evidence coverage counts claims that have acceptable evidence support.
    if total_claims:
        evidence_coverage = (
            (supported_claims + inferred_claims)
            / total_claims
        ) * 100
    else:
        evidence_coverage = 0.0

    warnings: list[str] = []

    if inflation_count:
        warnings.append(
            f"{inflation_count} claim(s) contain wording stronger "
            "than the cited evidence."
        )

    if weak_claims:
        warnings.append(
            f"{weak_claims} claim(s) require human review."
        )

    if unsupported_claims:
        warnings.append(
            f"{unsupported_claims} claim(s) have insufficient or "
            "missing evidence."
        )

    # Verification policy:
    #
    # PASSED:
    #   Every claim is supported or a clearly marked inference.
    #
    # REVIEW_REQUIRED:
    #   At least one weak claim, but no unsupported claims.
    #
    # FAILED:
    #   At least one unsupported claim.
    #
    if unsupported_claims > 0:
        status = VERIFICATION_FAILED
    elif weak_claims > 0:
        status = VERIFICATION_REVIEW_REQUIRED
    else:
        status = VERIFICATION_PASSED

    return VerificationResult(
        status=status,
        total_claims=total_claims,
        supported_claims=supported_claims,
        inferred_claims=inferred_claims,
        weak_claims=weak_claims,
        unsupported_claims=unsupported_claims,
        evidence_coverage=round(evidence_coverage, 2),
        inflation_count=inflation_count,
        assessments=assessments,
        warnings=warnings,
    )