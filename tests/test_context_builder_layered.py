from meeting.domain.context_builder import build_layered_context
from meeting.domain.models import Message


def test_build_layered_context():
    summary_messages = [
        Message(role="system", content="round_summary: {}", name="summary")
    ]
    private_memory = {"assumptions": ["a1"]}
    ctx = build_layered_context(
        meeting_id="m-1",
        run_id="r-1",
        round_index=2,
        speaker="Chief Architect",
        summary_messages=summary_messages,
        private_memory=private_memory,
        system_instructions="system",
        user_task="task",
        limits={"max_tokens": 256},
    )

    assert ctx.context_mode == "layered"
    assert ctx.public_messages == summary_messages
    assert ctx.private_memory == private_memory
    assert ctx.speaker == "Chief Architect"
