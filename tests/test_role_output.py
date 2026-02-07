import asyncio
import json

import pytest

from meeting.domain.models import Event, Message, ValidationError
from meeting.domain.state_machine import _run_speaker_turn
from meeting.domain.validators import parse_and_validate_role_output


class MemoryStorage:
    def __init__(self) -> None:
        self.events = []

    def append_event_dict(self, event):
        self.events.append(event)


class FakeRunner:
    def __init__(self, messages):
        self._messages = list(messages)
        self._index = 0

    async def run(self, ctx):
        content = self._messages[min(self._index, len(self._messages) - 1)]
        self._index += 1
        message = Message(
            role="assistant",
            content=content,
            name=ctx.speaker,
            ts_ms=0,
            meta=None,
        )
        yield Event(
            type="agent_message",
            run_id=ctx.run_id,
            ts_ms=0,
            actor=f"agent:{ctx.speaker}",
            payload={
                "message": {
                    "role": message.role,
                    "content": message.content,
                    "name": message.name,
                    "ts_ms": message.ts_ms,
                    "meta": message.meta,
                },
                "message_id": "msg-test",
                "round": ctx.round,
            },
        )


def _valid_role_output():
    return {
        "assumptions": ["a1"],
        "proposal": "p1",
        "tradeoffs": ["t1"],
        "risks": [{"risk": "r1", "impact": "M", "mitigation": "m1", "verification": "v1"}],
        "questions": ["q1"],
        "decision_recommendation": "d1",
    }


def test_parse_role_output_valid_json():
    payload = _valid_role_output()
    parsed = parse_and_validate_role_output(json.dumps(payload))
    assert parsed["proposal"] == "p1"


def test_parse_role_output_fenced_json():
    payload = _valid_role_output()
    text = f"```json\n{json.dumps(payload)}\n```"
    parsed = parse_and_validate_role_output(text)
    assert parsed["assumptions"] == ["a1"]


def test_parse_role_output_missing_key():
    payload = _valid_role_output()
    payload.pop("proposal")
    with pytest.raises(ValidationError):
        parse_and_validate_role_output(json.dumps(payload))


def test_role_output_repair_flow():
    invalid = json.dumps({"assumptions": []})
    valid = json.dumps(_valid_role_output())
    runner = FakeRunner([invalid, valid])
    storage = MemoryStorage()
    public_messages = []
    limits = {"validate_role_output": True, "role_repair_prompt": "repair"}

    _, parsed = asyncio.run(
        _run_speaker_turn(
            storage=storage,
            runner=runner,
            meeting_id="m-1",
            run_id="r-1",
            round_index=1,
            speaker="Chief Architect",
            public_messages=public_messages,
            summary_messages=[],
            private_memory={},
            system_text="system",
            user_task="task",
            limits=limits,
            context_mode="shared",
        )
    )

    assert parsed is not None
    assert parsed["decision_recommendation"] == "d1"
    assert any(
        event.get("type") == "error" and event.get("payload", {}).get("stage") == "role_output_validation"
        for event in storage.events
    )
