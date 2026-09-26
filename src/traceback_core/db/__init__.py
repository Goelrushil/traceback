"""TRACEBACK database package."""

from .database import Base, SessionLocal, engine, get_db
from .models import (
    ClaimRecord,
    Evidence,
    Investigation,
    ProvenanceEvent,
    Source,
)


def initialize_database() -> None:
    """Create all TRACEBACK database tables."""
    Base.metadata.create_all(bind=engine)


__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "Source",
    "Evidence",
    "Investigation",
    "ClaimRecord",
    "ProvenanceEvent",
    "initialize_database",
]