"""TRACEBACK FastAPI backend."""

import json
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from traceback_core.ai.analyzer import analyze_evidence
from traceback_core.claims.engine import assess_claims
from traceback_core.db import initialize_database
from traceback_core.db.database import get_db
from traceback_core.db.models import (
    ClaimRecord,
    Evidence,
    Investigation,
    Source,
)
from traceback_core.edits.service import record_human_correction
from traceback_core.ingestion.service import ingest_file
from traceback_core.provenance.service import build_peel
from traceback_core.receipts.service import (
    create_receipt,
    receipt_to_dict,
)
from traceback_core.verification.engine import verify_claims


app = FastAPI(
    title="TRACEBACK API",
    version="0.1.0",
    description="AI provenance, verification and evidence intelligence.",
)


initialize_database()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------

class InvestigationRequest(BaseModel):
    question: str
    source_id: int


class CorrectionRequest(BaseModel):
    original_text: str
    corrected_text: str
    reason: str


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Basic API health check."""
    return {
        "status": "online",
        "service": "TRACEBACK",
    }


# ---------------------------------------------------------------------------
# SOURCES
# ---------------------------------------------------------------------------

@app.post("/sources/upload")
async def upload_source(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and ingest a supported evidence source."""

    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have a filename.",
        )

    suffix = Path(original_filename).suffix.lower()

    if not suffix:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have an extension.",
        )

    temp_dir = Path(
        tempfile.mkdtemp(prefix="traceback_upload_")
    )

    temporary_path = temp_dir / original_filename

    try:
        temporary_path.write_bytes(await file.read())

        source = ingest_file(
            db,
            temporary_path,
        )

    finally:
        temporary_path.unlink(missing_ok=True)
        temp_dir.rmdir()

    return {
        "source_id": source.source_id,
        "filename": source.filename,
        "source_type": source.source_type,
        "version": source.version,
        "content_hash": source.content_hash,
    }


@app.get("/sources")
def get_sources(
    db: Session = Depends(get_db),
):
    """Return all ingested sources."""

    sources = (
        db.query(Source)
        .order_by(Source.created_at.desc())
        .all()
    )

    return [
        {
            "source_id": source.source_id,
            "filename": source.filename,
            "source_type": source.source_type,
            "version": source.version,
            "content_hash": source.content_hash,
            "created_at": source.created_at.isoformat(),
        }
        for source in sources
    ]


@app.get("/sources/{source_id}/evidence")
def get_source_evidence(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Return evidence belonging to a source."""

    source = db.get(Source, source_id)

    if source is None:
        raise HTTPException(
            status_code=404,
            detail="Source not found.",
        )

    evidence = (
        db.query(Evidence)
        .filter(Evidence.source_id == source_id)
        .order_by(Evidence.evidence_id.asc())
        .all()
    )

    return [
        {
            "evidence_id": f"E{item.evidence_id}",
            "content": item.content,
            "locator": item.locator,
            "content_hash": item.content_hash,
        }
        for item in evidence
    ]


# ---------------------------------------------------------------------------
# INVESTIGATIONS
# ---------------------------------------------------------------------------

@app.post("/investigations")
def run_investigation(
    request: InvestigationRequest,
    db: Session = Depends(get_db),
):
    """
    Run and persist the complete TRACEBACK pipeline.

    Evidence → Gemini → Claims → Claim Engine
    → Verification → Investigation → Receipt
    """

    # 1. Validate selected source
    source = (
        db.query(Source)
        .filter(Source.source_id == request.source_id)
        .first()
    )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=f"Source {request.source_id} not found.",
        )

    # 2. Load ONLY evidence belonging to this source
    evidence_records = (
        db.query(Evidence)
        .filter(Evidence.source_id == request.source_id)
        .order_by(Evidence.evidence_id.asc())
        .all()
    )

    if not evidence_records:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence found for source {request.source_id}.",
        )

    evidence = [
        {
            "evidence_id": f"E{item.evidence_id}",
            "content": item.content,
        }
        for item in evidence_records
    ]

    # 3. AI analysis
    analysis = analyze_evidence(
        question=request.question,
        evidence=evidence,
    )

    evidence_by_id = {
        item["evidence_id"]: item["content"]
        for item in evidence
    }

    # 4. Deterministic claim assessment
    assessments = assess_claims(
        claims=analysis.claims,
        evidence_by_id=evidence_by_id,
    )

    # 5. Deterministic verification
    verification = verify_claims(
        claims=analysis.claims,
        evidence_by_id=evidence_by_id,
    )

    # 6. Create persistent investigation
    public_id = (
        f"TR-2026-{uuid.uuid4().hex[:8].upper()}"
    )

    investigation = Investigation(
        public_id=public_id,
        question=request.question,
        final_answer=analysis.answer,
        verification_status=verification.status,
    )

    db.add(investigation)
    db.flush()

    # 7. Persist claims
    claims_response = []

    for claim, assessment in zip(
        analysis.claims,
        assessments,
    ):
        claim_record = ClaimRecord(
            investigation_id=investigation.investigation_id,
            claim_id=claim.claim_id,
            text=claim.text,
            claim_type=claim.claim_type,
            health=assessment.health,
            inflation_detected=assessment.inflation_detected,
            reason=assessment.reason,
            suggested_rewrite=assessment.suggested_rewrite,
            evidence_ids=json.dumps(
                claim.evidence_ids
            ),
        )

        db.add(claim_record)

        claims_response.append(
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "claim_type": claim.claim_type,
                "evidence_ids": claim.evidence_ids,
                "health": assessment.health,
                "inflation_detected": (
                    assessment.inflation_detected
                ),
                "reason": assessment.reason,
                "suggested_rewrite": (
                    assessment.suggested_rewrite
                ),
            }
        )

    db.commit()
    db.refresh(investigation)

    # 8. Create tamper-evident receipt
    receipt = create_receipt(
        investigation_id=investigation.public_id,
        final_answer=analysis.answer,
        claims=claims_response,
        verification={
            "status": verification.status,
            "total_claims": verification.total_claims,
            "supported_claims": (
                verification.supported_claims
            ),
            "inferred_claims": (
                verification.inferred_claims
            ),
            "weak_claims": verification.weak_claims,
            "unsupported_claims": (
                verification.unsupported_claims
            ),
            "evidence_coverage": (
                verification.evidence_coverage
            ),
            "inflation_count": (
                verification.inflation_count
            ),
        },
    )

    return {
        "investigation_id": investigation.public_id,
        "source": {
            "source_id": source.source_id,
            "filename": source.filename,
            "source_type": source.source_type,
            "version": source.version,
            "content_hash": source.content_hash,
        },
        "question": request.question,
        "answer": analysis.answer,
        "claims": claims_response,
        "verification": {
            "status": verification.status,
            "total_claims": verification.total_claims,
            "supported_claims": (
                verification.supported_claims
            ),
            "inferred_claims": (
                verification.inferred_claims
            ),
            "weak_claims": verification.weak_claims,
            "unsupported_claims": (
                verification.unsupported_claims
            ),
            "evidence_coverage": (
                verification.evidence_coverage
            ),
            "inflation_count": (
                verification.inflation_count
            ),
            "warnings": verification.warnings,
        },
        "receipt": receipt_to_dict(receipt),
    }


@app.get("/investigations")
def get_investigations(
    db: Session = Depends(get_db),
):
    """Return persisted investigations."""

    investigations = (
        db.query(Investigation)
        .order_by(Investigation.created_at.desc())
        .all()
    )

    return [
        {
            "investigation_id": item.public_id,
            "question": item.question,
            "final_answer": item.final_answer,
            "verification_status": (
                item.verification_status
            ),
            "created_at": item.created_at.isoformat(),
        }
        for item in investigations
    ]


@app.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
):
    """Return a persisted investigation and its claims."""

    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.public_id == investigation_id
        )
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found.",
        )

    claims = (
        db.query(ClaimRecord)
        .filter(
            ClaimRecord.investigation_id
            == investigation.investigation_id
        )
        .order_by(ClaimRecord.claim_record_id.asc())
        .all()
    )

    return {
        "investigation_id": investigation.public_id,
        "question": investigation.question,
        "answer": investigation.final_answer,
        "verification_status": (
            investigation.verification_status
        ),
        "created_at": investigation.created_at.isoformat(),
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "claim_type": claim.claim_type,
                "health": claim.health,
                "inflation_detected": (
                    claim.inflation_detected
                ),
                "reason": claim.reason,
                "suggested_rewrite": (
                    claim.suggested_rewrite
                ),
                "evidence_ids": json.loads(
                    claim.evidence_ids
                ),
            }
            for claim in claims
        ],
    }


# ---------------------------------------------------------------------------
# PEEL / PROVENANCE
# ---------------------------------------------------------------------------

@app.get("/claims/{claim_id}/peel")
def get_peel(
    claim_id: str,
    db: Session = Depends(get_db),
):
    """Return persisted claim provenance through PEEL."""

    claim_record = (
        db.query(ClaimRecord)
        .filter(
            ClaimRecord.claim_id == claim_id
        )
        .order_by(
            ClaimRecord.claim_record_id.desc()
        )
        .first()
    )

    if claim_record is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    evidence_ids = json.loads(
        claim_record.evidence_ids
    )

    claim = type(
        "PersistedClaim",
        (),
        {
            "claim_id": claim_record.claim_id,
            "text": claim_record.text,
            "claim_type": claim_record.claim_type,
            "evidence_ids": evidence_ids,
        },
    )()

    assessment = type(
        "PersistedAssessment",
        (),
        {
            "health": claim_record.health,
            "inflation_detected": (
                claim_record.inflation_detected
            ),
            "reason": claim_record.reason or "",
            "suggested_rewrite": (
                claim_record.suggested_rewrite
            ),
        },
    )()

    peel = build_peel(
        db=db,
        claim=claim,
        assessment=assessment,
    )

    return {
        "claim_id": peel.claim_id,
        "claim_text": peel.claim_text,
        "claim_type": peel.claim_type,
        "health": peel.health,
        "inflation_detected": (
            peel.inflation_detected
        ),
        "reason": peel.reason,
        "suggested_rewrite": peel.suggested_rewrite,
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "content": item.content,
                "locator": item.locator,
                "content_hash": item.content_hash,
            }
            for item in peel.evidence
        ],
        "sources": [
            {
                "source_id": item.source_id,
                "filename": item.filename,
                "source_type": item.source_type,
                "version": item.version,
                "content_hash": item.content_hash,
                "created_at": item.created_at.isoformat(),
            }
            for item in peel.sources
        ],
    }


# ---------------------------------------------------------------------------
# HUMAN CORRECTIONS
# ---------------------------------------------------------------------------

@app.post("/claims/{claim_id}/correction")
def correct_claim(
    claim_id: str,
    request: CorrectionRequest,
    db: Session = Depends(get_db),
):
    """Record a human correction without overwriting the original."""

    claim_record = (
        db.query(ClaimRecord)
        .filter(
            ClaimRecord.claim_id == claim_id
        )
        .order_by(
            ClaimRecord.claim_record_id.desc()
        )
        .first()
    )

    if claim_record is None:
        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    correction = record_human_correction(
        db=db,
        claim_id=claim_id,
        original_text=request.original_text,
        corrected_text=request.corrected_text,
        reason=request.reason,
    )

    return asdict(correction)