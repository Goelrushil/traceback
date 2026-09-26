"""TRACEBACK V0.3 AI analysis schemas."""

from dataclasses import dataclass, field


@dataclass
class Claim:
    """A material claim produced by AI analysis."""

    claim_id: str
    text: str
    evidence_ids: list[str] = field(default_factory=list)
    claim_type: str = "factual"


@dataclass
class AnalysisResult:
    """Structured result returned by the TRACEBACK analysis engine."""

    answer: str
    claims: list[Claim] = field(default_factory=list)
