"""Context assembly for the Runner inputs."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import ExecutionContext, Message


# build_shared_context: assemble shared context for runner input.
def build_shared_context(
    meeting_id: str,
    run_id: str,
    round_index: int,
    speaker: str,
    public_messages: List[Message],
    system_instructions: str,
    user_task: str,
    limits: Dict[str, Any],
) -> ExecutionContext:
    # MVP: shared context only (no private memory).
    return ExecutionContext(
        meeting_id=meeting_id,
        run_id=run_id,
        round=round_index,
        speaker=speaker,
        context_mode="shared",
        public_messages=public_messages,
        private_memory={},
        system_instructions=system_instructions,
        user_task=user_task,
        limits=limits,
    )


def build_layered_context(
    meeting_id: str,
    run_id: str,
    round_index: int,
    speaker: str,
    summary_messages: List[Message],
    private_memory: Dict[str, Any],
    system_instructions: str,
    user_task: str,
    limits: Dict[str, Any],
) -> ExecutionContext:
    # Layered context: public summaries + role private memory.
    return ExecutionContext(
        meeting_id=meeting_id,
        run_id=run_id,
        round=round_index,
        speaker=speaker,
        context_mode="layered",
        public_messages=summary_messages,
        private_memory=private_memory,
        system_instructions=system_instructions,
        user_task=user_task,
        limits=limits,
    )
