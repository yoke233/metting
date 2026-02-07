from meeting.domain.artifacts import validate_consensus
from meeting.domain.models import ValidationError
from meeting.domain.state_machine import _compute_consensus


def test_compute_consensus_majority():
    outputs = {
        "A": {"decision_recommendation": "方案一"},
        "B": {"decision_recommendation": "方案二"},
        "C": {"decision_recommendation": "方案一"},
    }
    votes, winner, score = _compute_consensus(outputs)
    assert votes["方案一"] == 2
    assert winner == "方案一"
    assert score == 2 / 3


def test_validate_consensus_schema():
    consensus = {
        "round": 1,
        "votes": {"方案一": 2},
        "winner": "方案一",
        "rationale": "多数票收敛",
    }
    validate_consensus(consensus)


def test_validate_consensus_missing_key():
    consensus = {
        "round": 1,
        "votes": {"方案一": 2},
        "winner": "方案一",
    }
    try:
        validate_consensus(consensus)
        assert False, "should raise ValidationError"
    except ValidationError:
        assert True
