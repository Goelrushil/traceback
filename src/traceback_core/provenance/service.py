"""TRACEBACK provenance and PEEL service."""

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from traceback_core.ai.schemas import Claim
from traceback_core.claims.engine import ClaimAssessment
from traceback_core.db.models import Evidence, Source


@dataclass
class PEELSource:
    """Source information exposed by PEEL."""

    source_id: int
    filename: str
    source_type: str
    version: int
    content_hash: str
    created_at: datetime


@dataclass
class PEELEvidence:
    """Evidence information exposed by PEEL."""

    evidence_id: str
    content: str
    locator: str | None
    content_hash: str


@dataclass
class PEELResult:
    """Complete claim-to-source provenance view."""

    claim_id: str
    claim_text: str
    claim_type: str

    health: str
    inflation_detected: bool
    reason: str

    evidence: list[PEELEvidence] = field(default_factory=list)
    sources: list[PEELSource] = field(default_factory=list)

    suggested_rewrite: str | None = None


def build_peel(
    db: Session,
    claim: Claim,
    assessment: ClaimAssessment,
) -> PEELResult:
    """Build the PEEL view using persisted evidence and source records."""

    evidence_items: list[PEELEvidence] = []
    source_items: list[PEELSource] = []

    source_ids_seen: set[int] = set()

    for evidence_id in claim.evidence_ids:
        if not evidence_id.startswith("E"):
            continue

        try:
            numeric_id = int(evidence_id[1:])
        except ValueError:
            continue

        evidence_record = db.scalars(
            select(Evidence).where(
                Evidence.evidence_id == numeric_id
            )
        ).first()

        if evidence_record is None:
            continue

        evidence_items.append(
            PEELEvidence(
                evidence_id=evidence_id,
                content=evidence_record.content,
                locator=evidence_record.locator,
                content_hash=evidence_record.content_hash,
            )
        )

        if evidence_record.source_id in source_ids_seen:
            continue

        source_ids_seen.add(evidence_record.source_id)

        source_record = db.scalars(
            select(Source).where(
                Source.source_id == evidence_record.source_id
            )
        ).first()

        if source_record is not None:
            source_items.append(
                PEELSource(
                    source_id=source_record.source_id,
                    filename=source_record.filename,
                    source_type=source_record.source_type,
                    version=source_record.version,
                    content_hash=source_record.content_hash,
                    created_at=source_record.created_at,
                )
            )

    return PEELResult(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        claim_type=claim.claim_type,
        health=assessment.health,
        inflation_detected=assessment.inflation_detected,
        reason=assessment.reason,
        evidence=evidence_items,
        sources=source_items,
        suggested_rewrite=assessment.suggested_rewrite,
    )