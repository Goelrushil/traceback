"""TRACEBACK tamper-evident provenance receipt service."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import uuid


@dataclass
class Receipt:
    """Immutable machine-readable record of a TRACEBACK investigation."""

    receipt_id: str
    investigation_id: str
    final_answer: str

    claims: list[dict] = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    human_corrections: list[dict] = field(default_factory=list)

    created_at: str = ""
    integrity_hash: str = ""


def _canonical_payload(receipt: Receipt) -> dict:
    """Return the receipt data used to calculate its integrity hash."""

    return {
        "receipt_id": receipt.receipt_id,
        "investigation_id": receipt.investigation_id,
        "final_answer": receipt.final_answer,
        "claims": receipt.claims,
        "verification": receipt.verification,
        "human_corrections": receipt.human_corrections,
        "created_at": receipt.created_at,
    }


def calculate_integrity_hash(receipt: Receipt) -> str:
    """Calculate a deterministic SHA-256 hash for a receipt."""

    payload = _canonical_payload(receipt)

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


def create_receipt(
    investigation_id: str,
    final_answer: str,
    claims: list[dict],
    verification: dict,
    human_corrections: list[dict] | None = None,
) -> Receipt:
    """Create a new TRACEBACK provenance receipt."""

    created_at = datetime.now(timezone.utc).isoformat()

    receipt = Receipt(
        receipt_id=f"TR-{uuid.uuid4().hex[:12].upper()}",
        investigation_id=investigation_id,
        final_answer=final_answer,
        claims=claims,
        verification=verification,
        human_corrections=human_corrections or [],
        created_at=created_at,
    )

    receipt.integrity_hash = calculate_integrity_hash(receipt)

    return receipt


def verify_receipt_integrity(receipt: Receipt) -> bool:
    """Verify that a receipt has not changed since its hash was created."""

    expected_hash = calculate_integrity_hash(receipt)

    return expected_hash == receipt.integrity_hash


def receipt_to_dict(receipt: Receipt) -> dict:
    """Convert a receipt into a JSON-compatible dictionary."""

    return asdict(receipt)


def receipt_to_json(receipt: Receipt) -> str:
    """Serialize a receipt as stable, readable JSON."""

    return json.dumps(
        receipt_to_dict(receipt),
        indent=2,
        ensure_ascii=False,
    )