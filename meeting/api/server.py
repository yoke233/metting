"""FastAPI entrypoints for meeting creation and execution."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from meeting.domain.pause_resume import find_last_pause_token, make_resume_event
from meeting.config import get_role_prompts
from meeting.domain.state_machine import next_round_from_events, run_meeting
from meeting.runners.langchain_runner import create_runner
from meeting.storage.repo import StorageRepo


def _now_ms() -> int:
    # Timestamp helper for user message events.
    import time

    return int(time.time() * 1000)


class MeetingCreate(BaseModel):
    title: str = Field(default="")
    topic: str
    background: str = Field(default="")
    constraints: Dict[str, Any] = Field(default_factory=dict)
    roles: List[str] = Field(default_factory=list)
    max_rounds: int = 6
    context_mode: str = "shared"
    termination: Dict[str, Any] = Field(default_factory=dict)
    output_schema: str = "v1"
    pause_on_round: Optional[int] = None
    role_prompts: Dict[str, str] = Field(default_factory=dict)


class UserMessage(BaseModel):
    content: str


class ResumeRequest(BaseModel):
    resume_token: str
    answers: Dict[str, Any] = Field(default_factory=dict)


class RunStartRequest(BaseModel):
    overrides: Dict[str, Any] = Field(default_factory=dict)


def _build_user_task(config: Dict[str, Any]) -> str:
    # Merge topic/background/constraints into a single prompt string.
    topic = config.get("topic", "")
    background = config.get("background", "")
    constraints = config.get("constraints", {})
    return f"{topic}\n{background}\n{json.dumps(constraints)}".strip()


def _user_message_event(run_id: str, content: str) -> Dict[str, Any]:
    # Represent user input as an agent_message event for replay.
    message_id = f"msg-{uuid.uuid4().hex}"
    payload = {
        "message": {
            "role": "user",
            "content": content,
            "name": "user",
            "ts_ms": _now_ms(),
            "meta": None,
        },
        "message_id": message_id,
        "round": None,
        "event_code": "USER_MESSAGE_ADDED",
    }
    return {
        "type": "agent_message",
        "run_id": run_id,
        "ts_ms": _now_ms(),
        "actor": "user",
        "payload": payload,
    }


def _format_sse(event: Dict[str, Any]) -> str:
    # Format SSE payload for event streaming.
    data = json.dumps(event, ensure_ascii=False)
    return f"id: {event.get('id', 0)}\ndata: {data}\n\n"


def _merge_config(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    # Merge overrides into the base config (deep merge for nested dicts).
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


# create_app: FastAPI factory for the meeting service.
def create_app(db_path: Path | str = "meeting.db") -> FastAPI:
    app = FastAPI(title="Meeting System MVP")

    # Shared app state for storage and runner.
    app.state.storage = StorageRepo(Path(db_path))
    app.state.runner = create_runner()

    # Serve static UI files from docs/ at /static.
    app.mount("/static", StaticFiles(directory="docs"), name="static")

    @app.post("/meetings")
    def create_meeting(payload: MeetingCreate):
        # Persist meeting config.
        config = payload.model_dump()
        if not config.get("role_prompts"):
            config["role_prompts"] = get_role_prompts()
        meeting_id = app.state.storage.create_meeting(config)
        return {"meeting_id": meeting_id, "config": config}

    @app.get("/meetings")
    def list_meetings(limit: int = 100):
        # List recent meetings.
        meetings = app.state.storage.list_meetings(limit=limit)
        return {"meetings": meetings}

    @app.get("/meetings/{meeting_id}/runs")
    def list_runs_for_meeting(meeting_id: str, limit: int = 100):
        # List runs for a specific meeting.
        meeting = app.state.storage.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="meeting not found")
        runs = app.state.storage.list_runs(limit=limit, meeting_id=meeting_id)
        return {"meeting_id": meeting_id, "runs": runs}

    @app.get("/runs")
    def list_runs(limit: int = 100):
        # List recent runs across all meetings.
        runs = app.state.storage.list_runs(limit=limit)
        return {"runs": runs}

    @app.post("/meetings/{meeting_id}/runs")
    async def start_run(meeting_id: str, payload: RunStartRequest | None = None):
        # Start a new run and execute immediately.
        meeting = app.state.storage.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="meeting not found")
        config = json.loads(meeting["config_json"])
        overrides = payload.overrides if payload else {}
        run_config = _merge_config(config, overrides) if overrides else config
        run_id = app.state.storage.create_run(meeting_id, run_config)
        user_task = _build_user_task(run_config)
        result = await run_meeting(
            storage=app.state.storage,
            runner=app.state.runner,
            meeting_id=meeting_id,
            run_id=run_id,
            config=run_config,
            user_task=user_task,
            start_round=1,
        )
        return {"run_id": run_id, "status": result.get("status"), "artifacts": result.get("artifacts")}

    @app.post("/meetings/{meeting_id}/runs/{run_id}/messages")
    def add_message(meeting_id: str, run_id: str, payload: UserMessage):
        # Append user input to the event stream.
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        app.state.storage.append_event_dict(_user_message_event(run_id, payload.content))
        return {"status": "OK"}

    @app.post("/meetings/{meeting_id}/runs/{run_id}/resume")
    async def resume_run(meeting_id: str, run_id: str, payload: ResumeRequest):
        # Resume a paused run with answers.
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        config = json.loads(run["config_json"])
        events = app.state.storage.list_events(run_id)
        expected = find_last_pause_token(events)
        if expected and payload.resume_token != expected:
            raise HTTPException(status_code=400, detail="invalid resume token")

        resume_event = make_resume_event(run_id, payload.resume_token, payload.answers)
        app.state.storage.append_event_dict(
            {
                "type": resume_event.type,
                "run_id": resume_event.run_id,
                "ts_ms": resume_event.ts_ms,
                "actor": resume_event.actor,
                "payload": {**resume_event.payload, "event_code": "RESUMED"},
            }
        )

        start_round = next_round_from_events(events)
        app.state.storage.set_run_status(run_id, "RUNNING")
        user_task = _build_user_task(config)
        result = await run_meeting(
            storage=app.state.storage,
            runner=app.state.runner,
            meeting_id=meeting_id,
            run_id=run_id,
            config=config,
            user_task=user_task,
            start_round=start_round,
        )
        return {"run_id": run_id, "status": result.get("status"), "artifacts": result.get("artifacts")}

    @app.get("/meetings/{meeting_id}/runs/{run_id}")
    def get_run(meeting_id: str, run_id: str):
        # Return run status and artifacts.
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        artifacts = app.state.storage.list_artifacts(run_id)
        return {"run": run, "artifacts": artifacts}

    @app.get("/meetings/{meeting_id}/runs/{run_id}/events")
    def get_events(meeting_id: str, run_id: str, include_tokens: bool = True):
        # Return ordered event stream for replay.
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        events = app.state.storage.list_events(run_id)
        if not include_tokens:
            events = [event for event in events if event.get("type") != "token"]
        return {"events": events}

    @app.get("/meetings/{meeting_id}/runs/{run_id}/events/stream")
    async def stream_events(
        meeting_id: str,
        run_id: str,
        after_id: Optional[int] = None,
        tail: int = 200,
        poll_ms: int = 1000,
    ):
        # Stream events using Server-Sent Events (SSE).
        run = app.state.storage.get_run(run_id)
        if not run or run.get("meeting_id") != meeting_id:
            raise HTTPException(status_code=404, detail="run not found")

        safe_tail = max(0, min(int(tail or 0), 500))
        safe_poll_ms = max(200, min(int(poll_ms or 1000), 5000))

        async def event_generator():
            # Yield recent events first, then poll for new ones.
            last_id = int(after_id or 0)
            if after_id is None and safe_tail:
                for event in app.state.storage.list_recent_event_rows(run_id, limit=safe_tail):
                    last_id = event["id"]
                    yield _format_sse(event)

            idle_cycles = 0
            keepalive_every = max(1, int(15000 / safe_poll_ms))

            while True:
                events = app.state.storage.list_event_rows_after(run_id, last_id, limit=200)
                if events:
                    idle_cycles = 0
                    for event in events:
                        last_id = event["id"]
                        yield _format_sse(event)
                else:
                    idle_cycles += 1
                    if idle_cycles % keepalive_every == 0:
                        yield ": keep-alive\n\n"
                await asyncio.sleep(safe_poll_ms / 1000)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @app.get("/meetings/{meeting_id}/runs/{run_id}/summaries")
    def get_summaries(meeting_id: str, run_id: str):
        # Return round summaries for a run.
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        summaries = app.state.storage.list_summaries(run_id)
        return {"summaries": summaries}

    @app.get("/meetings/{meeting_id}/runs/{run_id}/memories")
    def get_memories(meeting_id: str, run_id: str, role: Optional[str] = None):
        # Return private memories for a run (optionally filtered by role).
        run = app.state.storage.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        if role:
            memory = app.state.storage.get_memory(run_id, role)
            return {"role": role, "memory": memory}
        memories = app.state.storage.list_memories(run_id)
        return {"memories": memories}

    return app
