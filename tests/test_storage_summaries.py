def test_list_summaries(storage):
    summary1 = {
        "round": 1,
        "summary": "r1",
        "open_questions": [],
        "decisions": [],
        "risks": [],
        "next_steps": [],
    }
    summary2 = {
        "round": 2,
        "summary": "r2",
        "open_questions": [],
        "decisions": [],
        "risks": [],
        "next_steps": [],
    }
    storage.save_artifact("r-1", "SUMMARY", "v2", summary1)
    storage.save_artifact("r-1", "SUMMARY", "v2", summary2)

    summaries = storage.list_summaries("r-1")
    assert len(summaries) == 2
    assert summaries[0]["content"]["round"] == 1
    assert summaries[1]["content"]["round"] == 2
