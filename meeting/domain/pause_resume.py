"""Pause/resume protocol helpers."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from .models import Event


# create_resume_token: generate an opaque token for resume validation.
def create_resume_token() -> str:
    # Generate an opaque token to correlate resume requests.
    return f"resume-{uuid.uuid4().hex}"


# make_pause_event: build a pause event with missing-info questions.
def make_pause_event(
    run_id: str,
    reason: str,
    questions: List[Dict[str, Any]],
    actor: str = "system",
) -> Event:
    # Pause event captures missing info and questions.
    payload = {
        "pause_reason": reason,
        "questions": questions,
        "resume_token": create_resume_token(),
        "suggested_next": "answer_questions",
    }
    return Event(type="pause", run_id=run_id, ts_ms=_now_ms(), actor=actor, payload=payload)


# make_resume_event: build a resume event carrying user answers.
def make_resume_event(
    run_id: str,
    resume_token: str,
    answers: Dict[str, Any],
    actor: str = "user",
) -> Event:
    # Resume event carries the user's answers for re-entry.
    payload = {
        "resume_token": resume_token,
        "answers": answers,
    }
    return Event(type="resume", run_id=run_id, ts_ms=_now_ms(), actor=actor, payload=payload)


# find_last_pause_token: get the most recent pause token from events.
def find_last_pause_token(events: List[Dict[str, Any]]) -> Optional[str]:
    # Look backward for the latest pause token.
    for event in reversed(events):
        if event.get("type") == "pause":
            return event.get("payload", {}).get("resume_token")
    return None


def _now_ms() -> int:
    # Millisecond timestamp for events.
    import time

    return int(time.time() * 1000)
