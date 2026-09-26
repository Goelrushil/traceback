"""TRACEBACK V0.2 evidence ingestion service."""

import csv
import hashlib
import json
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from traceback_core.db.models import Evidence, Source


SUPPORTED_TYPES = {
    ".txt": "text",
    ".json": "json",
    ".csv": "csv",
    ".pdf": "pdf",
}


def calculate_hash(content: bytes) -> str:
    """Return a SHA-256 hash for content."""
    return hashlib.sha256(content).hexdigest()


def read_file(path: Path) -> str:
    """Read a supported file into normalized text."""
    suffix = path.suffix.lower()

    if suffix == ".txt":
        content = path.read_text(encoding="utf-8-sig")
        return content.lstrip("\ufeff")

    if suffix == ".json":
        data = json.loads(
            path.read_text(encoding="utf-8-sig")
        )
        return json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )

    if suffix == ".csv":
        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            rows = list(csv.reader(file))

        return "\n".join(
            " | ".join(row)
            for row in rows
        )

    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = page.extract_text() or ""

            if text.strip():
                pages.append(
                    f"[PAGE {page_number}]\n{text.strip()}"
                )

        return "\n".join(pages)

    raise ValueError(
        f"Unsupported file type: {suffix}"
    )


def split_into_evidence(content: str) -> list[str]:
    """Split normalized content into non-empty evidence units."""
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]


def find_existing_source(
    db: Session,
    filename: str,
    content_hash: str,
) -> Source | None:
    """Find an already-ingested identical source version."""
    statement = (
        select(Source)
        .where(
            Source.filename == filename,
            Source.content_hash == content_hash,
        )
        .order_by(Source.version.desc())
    )

    return db.scalars(statement).first()


def get_next_version(
    db: Session,
    filename: str,
) -> int:
    """Return the next version number for a filename."""
    statement = (
        select(Source)
        .where(Source.filename == filename)
        .order_by(Source.version.desc())
    )

    latest_source = db.scalars(statement).first()

    if latest_source is None:
        return 1

    return latest_source.version + 1


def ingest_file(
    db: Session,
    file_path: str | Path,
) -> Source:
    """Ingest a supported file with source version tracking."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(path)

    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_TYPES:
        raise ValueError(
            f"Unsupported file type: {suffix}. "
            f"Supported types: {', '.join(SUPPORTED_TYPES)}"
        )

    raw_bytes = path.read_bytes()
    content_hash = calculate_hash(raw_bytes)

    existing_source = find_existing_source(
        db,
        path.name,
        content_hash,
    )

    if existing_source is not None:
        return existing_source

    content = read_file(path)

    version = get_next_version(
        db,
        path.name,
    )

    source = Source(
        filename=path.name,
        source_type=SUPPORTED_TYPES[suffix],
        content_hash=content_hash,
        version=version,
    )

    db.add(source)
    db.flush()

    evidence_units = split_into_evidence(content)

    for index, evidence_text in enumerate(
        evidence_units,
        start=1,
    ):
        if evidence_text.startswith("[PAGE "):
            locator = f"document:page:{index}"
        else:
            locator = f"document:line:{index}"

        evidence = Evidence(
            source_id=source.source_id,
            content=evidence_text,
            locator=locator,
            content_hash=calculate_hash(
                evidence_text.encode("utf-8")
            ),
        )

        db.add(evidence)

    db.commit()
    db.refresh(source)

    return source
