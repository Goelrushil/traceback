"""TRACEBACK V0.3 AI analysis engine."""

import json

from traceback_core.ai.client import ask_gemini
from traceback_core.ai.schemas import AnalysisResult, Claim


def analyze_evidence(
    question: str,
    evidence: list[dict[str, str]],
) -> AnalysisResult:
    """Analyze stored evidence and extract material claims."""

    evidence_text = "\n".join(
        f"{item['evidence_id']}: {item['content']}"
        for item in evidence
    )

    prompt = f"""
You are the analysis engine for TRACEBACK.

TRACEBACK is an AI provenance and evidence verification platform.

Your job is to answer the user's question using ONLY the supplied evidence.

CRITICAL RULES:

1. Do not invent facts.
2. Do not invent evidence IDs.
3. Every material factual claim MUST reference one or more supplied evidence IDs.
4. If the evidence does not support a conclusion, say so.
5. Distinguish direct facts from inferences.
6. Avoid strengthening the wording beyond what the evidence supports.
7. Return ONLY valid JSON.
8. Do not provide chain-of-thought.

USER QUESTION:
{question}

AVAILABLE EVIDENCE:
{evidence_text}

Return exactly this JSON structure:

{{
  "answer": "concise answer to the user's question",
  "claims": [
    {{
      "claim_id": "C1",
      "text": "material claim",
      "evidence_ids": ["E1"],
      "claim_type": "factual"
    }}
  ]
}}

Allowed claim_type values:
- factual
- inference
- comparison
- conclusion
- limitation
"""

    raw_response = ask_gemini(prompt)

    data = json.loads(raw_response)

    claims = [
        Claim(
            claim_id=item["claim_id"],
            text=item["text"],
            evidence_ids=item.get("evidence_ids", []),
            claim_type=item.get("claim_type", "factual"),
        )
        for item in data.get("claims", [])
    ]

    return AnalysisResult(
        answer=data.get("answer", ""),
        claims=claims,
    )
