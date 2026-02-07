"""Role output parsing and validation helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from .models import ValidationError


def parse_and_validate_role_output(text: str) -> Dict[str, Any]:
    # Parse JSON text and validate required role output fields.
    payload = _load_json(text)
    validate_role_output(payload)
    return payload


def validate_role_output(payload: Dict[str, Any]) -> None:
    # Enforce role output schema required by the PRD.
    _require_keys(
        payload,
        [
            "assumptions",
            "proposal",
            "tradeoffs",
            "risks",
            "questions",
            "decision_recommendation",
        ],
    )
    _require_list(payload["assumptions"], "assumptions")
    _require_list(payload["tradeoffs"], "tradeoffs")
    _require_list(payload["questions"], "questions")
    _require_list(payload["risks"], "risks")
    for risk in payload["risks"]:
        if not isinstance(risk, dict):
            raise ValidationError("risks entries must be objects")
        _require_keys(risk, ["risk", "impact", "mitigation", "verification"])


def _require_keys(data: Dict[str, Any], keys: list[str]) -> None:
    # Shared helper for required keys.
    for key in keys:
        if key not in data:
            raise ValidationError(f"missing key: {key}")


def _require_list(value: Any, name: str) -> None:
    # Ensure a value is a list for schema validation.
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be list")


def _load_json(text: str) -> Dict[str, Any]:
    # Extract JSON from text and parse it into a dict.
    if not text:
        raise ValidationError("role output is empty")
    match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", text, flags=re.DOTALL)
    json_text = match.group(1) if match else _extract_json_object(text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("role output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationError("role output must be a JSON object")
    return payload


def _extract_json_object(text: str) -> str:
    # Extract the first top-level JSON object from free-form text.
    start = text.find("{")
    if start == -1:
        raise ValidationError("no JSON object found")
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise ValidationError("unterminated JSON object")
