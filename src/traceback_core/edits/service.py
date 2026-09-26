"""TRACEBACK human correction and provenance event service."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from traceback_core.db.models import ProvenanceEvent


@dataclass
class HumanCorrection:
    """A human-approved correction to an AI-generated claim."""

    claim_id: str
    original_text: str
    corrected_text: str
    reason: str
    event_id: int
    created_at: datetime


def record_human_correction(
    db: Session,
    claim_id: str,
    original_text: str,
    corrected_text: str,
    reason: str,
) -> HumanCorrection:
    """
    Persist a human correction as an immutable provenance event.

    The original AI wording is never overwritten.
    """

    event = ProvenanceEvent(
        event_type="human_correction",
        claim_id=claim_id,
        original_text=original_text,
        corrected_text=corrected_text,
        reason=reason,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return HumanCorrection(
        claim_id=claim_id,
        original_text=event.original_text or "",
        corrected_text=event.corrected_text or "",
        reason=event.reason or "",
        event_id=event.event_id,
        created_at=event.created_at,
    )


def get_claim_history(
    db: Session,
    claim_id: str,
) -> list[ProvenanceEvent]:
    """Return the complete provenance history for a claim."""

    return (
        db.query(ProvenanceEvent)
        .filter(ProvenanceEvent.claim_id == claim_id)
        .order_by(ProvenanceEvent.created_at.asc())
        .all()
    )