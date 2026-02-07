"""SQLite-backed storage for meetings, runs, events, and artifacts."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now_ms() -> int:
    # Consistent millisecond timestamps for storage rows.
    import time

    return int(time.time() * 1000)


class StorageRepo:
    def __init__(self, db_path: Path):
        # Initialize and ensure schema exists.
        self.db_path = Path(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        # Open a new SQLite connection with row access by name.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        # Create tables if they do not exist.
        schema_path = Path(__file__).with_name("schema.sql")
        schema = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)

    # create_meeting: insert a meeting row and return id.
    def create_meeting(self, config: Dict[str, Any]) -> str:
        # Persist a new meeting record.
        meeting_id = f"m-{_now_ms()}"
        title = config.get("title", "")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO meetings (id, title, config_json, created_at) VALUES (?, ?, ?, ?)",
                (meeting_id, title, json.dumps(config), _now_ms()),
            )
        return meeting_id

    def get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        # Fetch a meeting by id.
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    # list_meetings: list recent meetings.
    def list_meetings(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM meetings ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # create_run: insert a run row and return id.
    def create_run(self, meeting_id: str, config: Dict[str, Any]) -> str:
        # Persist a new run for a meeting.
        run_id = f"r-{_now_ms()}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (id, meeting_id, status, config_json, started_at, ended_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, meeting_id, "RUNNING", json.dumps(config), _now_ms(), None),
            )
        return run_id

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        # Fetch a run by id.
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    # list_runs: list runs, optionally filtered by meeting_id.
    def list_runs(self, limit: int = 100, meeting_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if meeting_id:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE meeting_id = ? ORDER BY started_at DESC LIMIT ?",
                    (meeting_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def set_run_status(self, run_id: str, status: str) -> None:
        # Update status and ended_at for terminal states.
        ended_at = _now_ms() if status in {"DONE", "FAILED"} else None
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, ended_at = ? WHERE id = ?",
                (status, ended_at, run_id),
            )

    # append_event_dict: append-only event write.
    def append_event_dict(self, event: Dict[str, Any]) -> None:
        # Append-only event storage.
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO events (run_id, ts_ms, type, actor, payload_json) VALUES (?, ?, ?, ?, ?)",
                (
                    event.get("run_id"),
                    event.get("ts_ms"),
                    event.get("type"),
                    event.get("actor"),
                    json.dumps(event.get("payload", {})),
                ),
            )

    # list_events: ordered replay of events.
    def list_events(self, run_id: str) -> List[Dict[str, Any]]:
        # Ordered event replay for a run.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, ts_ms, type, actor, payload_json FROM events WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        events: List[Dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            events.append(
                {
                    "run_id": row["run_id"],
                    "ts_ms": row["ts_ms"],
                    "type": row["type"],
                    "actor": row["actor"],
                    "payload": payload,
                }
            )
        return events

    # save_artifact: persist a structured artifact.
    def save_artifact(self, run_id: str, artifact_type: str, version: str, content: Dict[str, Any]) -> None:
        # Persist a structured artifact.
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO artifacts (run_id, type, version, content_json, created_ts_ms) VALUES (?, ?, ?, ?, ?)",
                (run_id, artifact_type, version, json.dumps(content), _now_ms()),
            )

    # list_artifacts: load artifacts for output.
    def list_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        # Load artifacts for response payloads.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, type, version, content_json, created_ts_ms FROM artifacts WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        artifacts: List[Dict[str, Any]] = []
        for row in rows:
            artifacts.append(
                {
                    "run_id": row["run_id"],
                    "type": row["type"],
                    "version": row["version"],
                    "content": json.loads(row["content_json"]),
                    "created_ts_ms": row["created_ts_ms"],
                }
            )
        return artifacts

    def list_summaries(self, run_id: str, version: str = "v2") -> List[Dict[str, Any]]:
        # Load round summaries for a run.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, type, version, content_json, created_ts_ms "
                "FROM artifacts WHERE run_id = ? AND type = ? AND version = ? ORDER BY created_ts_ms",
                (run_id, "SUMMARY", version),
            ).fetchall()
        summaries: List[Dict[str, Any]] = []
        for row in rows:
            summaries.append(
                {
                    "run_id": row["run_id"],
                    "type": row["type"],
                    "version": row["version"],
                    "content": json.loads(row["content_json"]),
                    "created_ts_ms": row["created_ts_ms"],
                }
            )
        return summaries

    def get_memory(self, run_id: str, role_name: str) -> Optional[Dict[str, Any]]:
        # Fetch the latest memory snapshot for a role.
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content_json FROM memories WHERE run_id = ? AND role_name = ? "
                "ORDER BY updated_ts_ms DESC LIMIT 1",
                (run_id, role_name),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["content_json"])

    def list_memories(self, run_id: str) -> List[Dict[str, Any]]:
        # Load latest memory snapshots per role.
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role_name, content_json, updated_ts_ms FROM memories WHERE run_id = ? "
                "ORDER BY updated_ts_ms DESC",
                (run_id,),
            ).fetchall()
        latest: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            role = row["role_name"]
            if role in latest:
                continue
            latest[role] = {
                "role_name": role,
                "content": json.loads(row["content_json"]),
                "updated_ts_ms": row["updated_ts_ms"],
            }
        return list(latest.values())

    def upsert_memory(self, run_id: str, role_name: str, content: Dict[str, Any]) -> None:
        # Append a new memory snapshot for the role.
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (run_id, role_name, content_json, updated_ts_ms) VALUES (?, ?, ?, ?)",
                (run_id, role_name, json.dumps(content), _now_ms()),
            )

    def save_memory(self, run_id: str, role_name: str, content: Dict[str, Any]) -> None:
        # Placeholder for layered context storage.
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (run_id, role_name, content_json, updated_ts_ms) VALUES (?, ?, ?, ?)",
                (run_id, role_name, json.dumps(content), _now_ms()),
            )
