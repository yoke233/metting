"""Artifact generation and validation helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .models import ValidationError


# validate_adr: enforce ADR schema.
def validate_adr(content: Dict[str, Any]) -> None:
    # ADR schema validation for MVP.
    required = [
        "context",
        "decision",
        "alternatives_considered",
        "consequences",
        "risks_summary",
        "open_questions",
        "next_steps",
    ]
    _require_keys(content, required)


# validate_tasks: enforce tasks schema.
def validate_tasks(content: Dict[str, Any]) -> None:
    # Tasks schema validation for MVP.
    _require_keys(content, ["tasks"])
    tasks = content["tasks"]
    if not isinstance(tasks, list):
        raise ValidationError("tasks must be list")
    for task in tasks:
        _require_keys(
            task,
            ["task_id", "title", "owner_role", "priority", "estimate", "dependencies"],
        )


# validate_risks: enforce risks schema.
def validate_risks(content: Dict[str, Any]) -> None:
    # Risks schema validation for MVP.
    _require_keys(content, ["risks"])
    risks = content["risks"]
    if not isinstance(risks, list):
        raise ValidationError("risks must be list")
    for risk in risks:
        _require_keys(
            risk,
            [
                "risk",
                "impact",
                "probability",
                "mitigation",
                "verification",
                "owner_role",
            ],
        )


# generate_adr: minimal ADR generator for MVP.
def generate_adr(public_messages: List[str], user_task: str) -> Dict[str, Any]:
    # Minimal placeholder ADR content for MVP.
    context = user_task or ""
    return {
        "context": context,
        "decision": "TBD",
        "alternatives_considered": [],
        "consequences": [],
        "risks_summary": [],
        "open_questions": [],
        "next_steps": [],
    }


# generate_tasks: minimal tasks generator for MVP.
def generate_tasks() -> Dict[str, Any]:
    # Minimal placeholder tasks list for MVP.
    return {
        "tasks": [
            {
                "task_id": "T1",
                "title": "Define ADR decision",
                "owner_role": "Chief Architect",
                "priority": "P1",
                "estimate": "S",
                "dependencies": [],
            }
        ]
    }


# generate_risks: minimal risks generator for MVP.
def generate_risks() -> Dict[str, Any]:
    # Minimal placeholder risks list for MVP.
    return {
        "risks": [
            {
                "risk": "Incomplete requirements",
                "impact": "M",
                "probability": "M",
                "mitigation": "Clarify scope and constraints",
                "verification": "Stakeholder review",
                "owner_role": "Recorder",
            }
        ]
    }


def parse_recorder_output(text: str) -> Dict[str, Dict[str, Any]]:
    # Parse Recorder JSON output into ADR/TASKS/RISKS dicts.
    payload = _load_recorder_json(text)
    adr = _get_case_insensitive(payload, "ADR")
    tasks = _get_case_insensitive(payload, "TASKS")
    risks = _get_case_insensitive(payload, "RISKS")
    if not isinstance(adr, dict):
        raise ValidationError("ADR must be object")
    # Accept TASKS as list and normalize to object shape for compatibility.
    if isinstance(tasks, list):
        tasks = {"tasks": tasks}
    if not isinstance(tasks, dict):
        raise ValidationError("TASKS must be object")
    if not isinstance(risks, dict):
        raise ValidationError("RISKS must be object")
    return {"ADR": adr, "TASKS": tasks, "RISKS": risks}


def validate_round_summary(content: Dict[str, Any]) -> None:
    # Validate per-round summary schema.
    _require_keys(
        content,
        ["round", "summary", "open_questions", "decisions", "risks", "next_steps"],
    )
    if not isinstance(content["round"], int):
        raise ValidationError("round must be int")
    if not isinstance(content["summary"], str):
        raise ValidationError("summary must be string")
    _require_list(content["open_questions"], "open_questions")
    _require_list(content["decisions"], "decisions")
    _require_list(content["risks"], "risks")
    _require_list(content["next_steps"], "next_steps")


def parse_round_summary_output(text: str, round_index: int) -> Dict[str, Any]:
    # Parse and validate Recorder round summary output.
    payload = _load_recorder_json(text)
    if "round" not in payload:
        payload["round"] = round_index
    validate_round_summary(payload)
    return payload


def validate_consensus(content: Dict[str, Any]) -> None:
    # Validate consensus artifact schema.
    _require_keys(content, ["round", "votes", "winner", "rationale"])
    if not isinstance(content["round"], int):
        raise ValidationError("round must be int")
    if not isinstance(content["votes"], dict):
        raise ValidationError("votes must be dict")
    if not isinstance(content["winner"], str):
        raise ValidationError("winner must be string")
    if not isinstance(content["rationale"], str):
        raise ValidationError("rationale must be string")


def generate_flowchart(roles: List[str], rounds: int) -> Dict[str, Any]:
    # Generate a Mermaid sequence diagram for the completed meeting.
    safe_rounds = max(1, int(rounds))
    speaker_roles = list(roles) if roles else ["Speaker"]
    used_roles: List[str] = []
    for idx in range(1, safe_rounds + 1):
        role = speaker_roles[(idx - 1) % len(speaker_roles)]
        if role not in used_roles:
            used_roles.append(role)
    participants = ["会议系统"] + used_roles
    if "Recorder" not in participants:
        participants.append("Recorder")

    alias_map: Dict[str, str] = {}
    lines: List[str] = ["sequenceDiagram", "  autonumber"]

    for idx, role in enumerate(participants):
        alias = f"p{idx}"
        alias_map[role] = alias
        label = _role_label(role)
        lines.append(f'  participant {alias} as "{label}"')

    system_alias = alias_map["会议系统"]
    recorder_alias = alias_map.get("Recorder", alias_map[participants[-1]])

    for idx in range(1, safe_rounds + 1):
        role = speaker_roles[(idx - 1) % len(speaker_roles)]
        speaker_alias = alias_map[role]
        lines.append(f"  {system_alias}->>{speaker_alias}: 第{idx}轮 发言")
        lines.append(f"  {speaker_alias}-->>{system_alias}: 第{idx}轮 结论")

    lines.append(f"  {system_alias}->>{recorder_alias}: 会后整理")
    lines.append(f"  {recorder_alias}-->>{system_alias}: 输出 ADR / TASKS / RISKS")
    return {"mermaid": "\n".join(lines), "rounds": safe_rounds, "roles": roles}


def _require_keys(data: Dict[str, Any], keys: List[str]) -> None:
    # Shared helper for schema checks.
    for key in keys:
        if key not in data:
            raise ValidationError(f"missing key: {key}")


def _require_list(value: Any, name: str) -> None:
    # Validate list types in artifacts.
    if not isinstance(value, list):
        raise ValidationError(f"{name} must be list")


def _role_label(role: str) -> str:
    # Map common role names to Chinese labels for display.
    mapping = {
        "Chief Architect": "首席架构师",
        "Infra Architect": "基础设施架构师",
        "Security Architect": "安全架构师",
        "Skeptic": "质疑者",
        "Recorder": "书记员",
        "Speaker": "发言者",
        "会议系统": "会议系统",
    }
    return mapping.get(role, str(role))


def _get_case_insensitive(data: Dict[str, Any], key: str) -> Any:
    # Fetch a value by case-insensitive key match.
    if key in data:
        return data[key]
    lookup = {str(k).lower(): v for k, v in data.items()}
    lowered = key.lower()
    if lowered in lookup:
        return lookup[lowered]
    raise ValidationError(f"missing key: {key}")


def _load_recorder_json(text: str) -> Dict[str, Any]:
    # Extract and parse JSON from Recorder output text.
    if not text:
        raise ValidationError("recorder output is empty")
    match = re.search(r"```(?:json)?\s*(\{.*?})\s*```", text, flags=re.DOTALL)
    json_text = match.group(1) if match else _extract_json_object(text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("recorder output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValidationError("recorder output must be a JSON object")
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
