import time
import uuid

import pytest


@pytest.fixture
def now_ms():
    return int(time.time() * 1000)


@pytest.fixture
def meeting_id():
    return f"m-{uuid.uuid4().hex}"


@pytest.fixture
def run_id():
    return f"r-{uuid.uuid4().hex}"


@pytest.fixture
def sample_message(now_ms):
    return {
        "role": "user",
        "content": "hello",
        "name": None,
        "ts_ms": now_ms,
        "meta": None,
    }


@pytest.fixture
def make_message(now_ms):
    def _make(role="user", content="hello", name=None, meta=None):
        return {
            "role": role,
            "content": content,
            "name": name,
            "ts_ms": now_ms,
            "meta": meta,
        }

    return _make


@pytest.fixture
def make_event(run_id, now_ms):
    def _make(event_type="round_started", actor="system", payload=None):
        return {
            "type": event_type,
            "run_id": run_id,
            "ts_ms": now_ms,
            "actor": actor,
            "payload": payload or {},
        }

    return _make


@pytest.fixture
def adr_content():
    return {
        "context": "test context",
        "decision": "test decision",
        "alternatives_considered": ["alt A", "alt B"],
        "consequences": ["cost increase"],
        "risks_summary": ["latency risk"],
        "open_questions": ["qps peak?"],
        "next_steps": ["validate load"],
    }


@pytest.fixture
def tasks_content():
    return {
        "tasks": [
            {
                "task_id": "T1",
                "title": "add cache",
                "owner_role": "Infra Architect",
                "priority": "P1",
                "estimate": "M",
                "dependencies": [],
            }
        ]
    }


@pytest.fixture
def risks_content():
    return {
        "risks": [
            {
                "risk": "cache stampede",
                "impact": "H",
                "probability": "M",
                "mitigation": "rate limit",
                "verification": "load test",
                "owner_role": "Security Architect",
            }
        ]
    }


@pytest.fixture
def sample_adr_artifact(run_id, now_ms, adr_content):
    return {
        "run_id": run_id,
        "type": "ADR",
        "version": "v1",
        "content": adr_content,
        "created_ts_ms": now_ms,
    }


@pytest.fixture
def sample_tasks_artifact(run_id, now_ms, tasks_content):
    return {
        "run_id": run_id,
        "type": "TASKS",
        "version": "v1",
        "content": tasks_content,
        "created_ts_ms": now_ms,
    }


@pytest.fixture
def sample_risks_artifact(run_id, now_ms, risks_content):
    return {
        "run_id": run_id,
        "type": "RISKS",
        "version": "v1",
        "content": risks_content,
        "created_ts_ms": now_ms,
    }


@pytest.fixture
def meeting_config():
    return {
        "title": "Test Meeting",
        "topic": "Test Topic",
        "background": "Test Background",
        "constraints": {},
        "roles": [
            "Chief Architect",
            "Infra Architect",
            "Security Architect",
            "Skeptic",
            "Recorder",
        ],
        "max_rounds": 3,
        "context_mode": "shared",
        "termination": {
            "max_rounds": 3,
            "open_questions_max": 2,
            "disagreements_max": 1,
        },
        "output_schema": "v1",
    }


@pytest.fixture
def sqlite_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def app():
    from meeting.api.server import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def storage(sqlite_path):
    from meeting.storage.repo import StorageRepo

    return StorageRepo(sqlite_path)
