from meeting.domain.state_machine import _select_parallel_speakers


def test_parallel_whitelist_order():
    roles = ["Chief Architect", "Infra Architect", "Security Architect", "Skeptic", "Recorder"]
    config = {"parallel_roles": ["Security Architect", "Chief Architect"]}
    speakers, strategy = _select_parallel_speakers(roles, 1, config)
    assert speakers == ["Security Architect", "Chief Architect"]
    assert strategy == "parallel_whitelist"


def test_parallel_subset_rotation():
    roles = ["A", "B", "C", "D"]
    config = {"parallel_role_limit": 2}
    speakers1, strategy1 = _select_parallel_speakers(roles, 1, config)
    speakers2, strategy2 = _select_parallel_speakers(roles, 2, config)
    assert speakers1 == ["A", "B"]
    assert speakers2 == ["C", "D"]
    assert strategy1 == "parallel_subset"
    assert strategy2 == "parallel_subset"
