import json

import pytest

from meeting.domain.artifacts import parse_round_summary_output
from meeting.domain.models import ValidationError


def _summary_payload():
    return {
        "round": 1,
        "summary": "本轮讨论缓存策略。",
        "open_questions": ["峰值 QPS？"],
        "decisions": ["采用读写分离"],
        "risks": ["缓存击穿"],
        "next_steps": ["补充压测数据"],
    }


def test_parse_round_summary_valid():
    payload = _summary_payload()
    parsed = parse_round_summary_output(json.dumps(payload), 1)
    assert parsed["round"] == 1


def test_parse_round_summary_fenced():
    payload = _summary_payload()
    text = f"```json\n{json.dumps(payload)}\n```"
    parsed = parse_round_summary_output(text, 1)
    assert parsed["summary"] == "本轮讨论缓存策略。"


def test_parse_round_summary_missing_key():
    payload = _summary_payload()
    payload.pop("summary")
    with pytest.raises(ValidationError):
        parse_round_summary_output(json.dumps(payload), 1)
