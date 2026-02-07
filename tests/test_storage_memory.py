def test_memory_roundtrip(storage):
    storage.upsert_memory("r-1", "Chief Architect", {"assumptions": ["a1"]})
    storage.upsert_memory("r-1", "Chief Architect", {"assumptions": ["a2"]})

    memory = storage.get_memory("r-1", "Chief Architect")
    assert memory == {"assumptions": ["a2"]}

    memories = storage.list_memories("r-1")
    assert memories
    roles = {item["role_name"] for item in memories}
    assert "Chief Architect" in roles
