"""TRACEBACK V0.3 AI analysis engine."""

import json
import re

from traceback_core.ai.client import ask_gemini
from traceback_core.ai.schemas import AnalysisResult, Claim


def _parse_json_response(raw_response: str) -> dict:
    """Safely extract a JSON object from Gemini's response."""

    if not raw_response or not raw_response.strip():
        raise ValueError("Gemini returned an empty response.")

    text = raw_response.strip()

    # Remove Markdown code fences if Gemini adds them.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    text = text.strip()

    # First attempt: response is already valid JSON.
    try:
        data = json.loads(text)

        if not isinstance(data, dict):
            raise ValueError("Gemini JSON response is not an object.")

        return data

    except json.JSONDecodeError:
        pass

    # Second attempt: find the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end > start:
        candidate = text[start:end + 1]

        try:
            data = json.loads(candidate)

            if not isinstance(data, dict):
                raise ValueError(
                    "Gemini JSON response is not an object."
                )

            return data

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Gemini returned malformed JSON."
            ) from exc

    raise ValueError(
        "Gemini did not return a valid JSON object."
    )


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
9. Do not wrap the JSON in Markdown code fences.
10. Do not add any text before or after the JSON.

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

    data = _parse_json_response(raw_response)

    # Only allow evidence IDs that actually exist.
    valid_evidence_ids = {
        item["evidence_id"]
        for item in evidence
    }

    claims = []

    for item in data.get("claims", []):
        evidence_ids = [
            evidence_id
            for evidence_id in item.get("evidence_ids", [])
            if evidence_id in valid_evidence_ids
        ]

        claims.append(
            Claim(
                claim_id=item["claim_id"],
                text=item["text"],
                evidence_ids=evidence_ids,
                claim_type=item.get(
                    "claim_type",
                    "factual",
                ),
            )
        )

    return AnalysisResult(
        answer=data.get("answer", ""),
        claims=claims,
    )