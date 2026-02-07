"""Core protocol types and lightweight validators for the meeting domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional


Role = Literal["system", "user", "assistant", "tool"]
EventType = Literal[
    "round_started",
    "speaker_selected",
    "token",
    "agent_message",
    "summary_written",
    "artifact_written",
    "pause",
    "resume",
    "metric",
    "error",
    "finished",
]
ArtifactType = Literal[
    "ADR",
    "TASKS",
    "RISKS",
    "MINUTES",
    "SUMMARY",
    "FLOWCHART",
    "CONSENSUS",
]
ContextMode = Literal["shared", "layered"]


class ValidationError(ValueError):
    # Raised when a protocol payload fails validation.
    pass


def _require(condition: bool, message: str) -> None:
    # Minimal helper to keep validators readable.
    if not condition:
        raise ValidationError(message)


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    name: Optional[str] = None
    ts_ms: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class Event:
    type: EventType
    run_id: str
    ts_ms: int
    actor: str
    payload: Dict[str, Any]


@dataclass(frozen=True)
class Artifact:
    run_id: str
    type: ArtifactType
    version: str
    content: Dict[str, Any]
    created_ts_ms: int


@dataclass(frozen=True)
class ExecutionContext:
    meeting_id: str
    run_id: str
    round: int
    speaker: str
    context_mode: ContextMode
    public_messages: List[Message]
    private_memory: Dict[str, Any]
    system_instructions: str
    user_task: str
    limits: Dict[str, Any]


def validate_message_dict(data: Dict[str, Any]) -> None:
    # Ensure incoming message payload matches the stable protocol.
    _require("role" in data, "message.role is required")
    _require("content" in data, "message.content is required")
    _require(data["role"] in {"system", "user", "assistant", "tool"}, "invalid message.role")
    _require(isinstance(data["content"], str) and data["content"], "message.content must be non-empty string")


def validate_event_dict(data: Dict[str, Any]) -> None:
    # Validate event payloads used for replay and audit.
    _require("type" in data, "event.type is required")
    _require("run_id" in data, "event.run_id is required")
    _require("ts_ms" in data, "event.ts_ms is required")
    _require("actor" in data, "event.actor is required")
    _require("payload" in data, "event.payload is required")
    _require(
        data["type"]
        in {
            "round_started",
            "speaker_selected",
            "token",
            "agent_message",
            "summary_written",
            "artifact_written",
            "pause",
            "resume",
            "metric",
            "error",
            "finished",
        },
        "invalid event.type",
    )
    _require(isinstance(data["payload"], dict), "event.payload must be dict")


def validate_artifact_dict(data: Dict[str, Any]) -> None:
    # Validate artifact payloads before storage or output.
    _require("run_id" in data, "artifact.run_id is required")
    _require("type" in data, "artifact.type is required")
    _require("version" in data, "artifact.version is required")
    _require("content" in data, "artifact.content is required")
    _require(
        data["type"]
        in {"ADR", "TASKS", "RISKS", "MINUTES", "SUMMARY", "FLOWCHART", "CONSENSUS"},
        "invalid artifact.type",
    )
    _require(isinstance(data["content"], dict), "artifact.content must be dict")


def validate_execution_context(ctx: ExecutionContext) -> None:
    # Guard rails for Runner inputs.
    _require(bool(ctx.meeting_id), "meeting_id is required")
    _require(bool(ctx.run_id), "run_id is required")
    _require(ctx.round >= 1, "round must be >= 1")
    _require(bool(ctx.speaker), "speaker is required")
    _require(ctx.context_mode in {"shared", "layered"}, "invalid context_mode")
    _require(isinstance(ctx.public_messages, list), "public_messages must be list")
    _require(isinstance(ctx.private_memory, dict), "private_memory must be dict")
    _require(isinstance(ctx.limits, dict), "limits must be dict")
