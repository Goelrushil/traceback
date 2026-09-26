"""TRACEBACK V0.2 database models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    """A source document or structured input."""

    __tablename__ = "sources"

    source_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )


class Evidence(Base):
    """An evidence item extracted from a source."""

    __tablename__ = "evidence"

    evidence_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.source_id"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    locator: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    source: Mapped[Source] = relationship(
        back_populates="evidence",
    )
class ProvenanceEvent(Base):
    """Immutable audit event for TRACEBACK provenance."""

    __tablename__ = "provenance_events"

    event_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    claim_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    original_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    corrected_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
class Investigation(Base):
    """Persisted TRACEBACK investigation."""

    __tablename__ = "investigations"

    investigation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    public_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    final_answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    verification_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class ClaimRecord(Base):
    """Persisted AI claim belonging to an investigation."""

    __tablename__ = "claims"

    claim_record_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.investigation_id"),
        nullable=False,
    )

    claim_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    claim_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    health: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    inflation_detected: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    suggested_rewrite: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence_ids: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )