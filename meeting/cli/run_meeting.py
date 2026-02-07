"""CLI entrypoints for running, resuming, and replaying meetings."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from meeting.domain.pause_resume import find_last_pause_token, make_resume_event
from meeting.config import get_role_prompts
from meeting.domain.state_machine import next_round_from_events, run_meeting
from meeting.runners.langchain_runner import create_runner
from meeting.storage.repo import StorageRepo


def _build_user_task(config: dict) -> str:
    # Combine topic/background/constraints into a prompt string.
    topic = config.get("topic", "")
    background = config.get("background", "")
    constraints = config.get("constraints", {})
    return f"{topic}\n{background}\n{json.dumps(constraints)}".strip()


def _load_json(path: Path) -> dict:
    # Read JSON config files.
    return json.loads(path.read_text(encoding="utf-8"))


# cmd_run: CLI handler to start a run.
def cmd_run(args: argparse.Namespace) -> int:
    # Start a new meeting run from config.
    storage = StorageRepo(Path(args.db))
    runner = create_runner()
    config = _load_json(Path(args.config))
    if not config.get("role_prompts"):
        config["role_prompts"] = get_role_prompts()
    meeting_id = storage.create_meeting(config)
    run_id = storage.create_run(meeting_id, config)
    user_task = _build_user_task(config)
    result = asyncio.run(
        run_meeting(
            storage=storage,
            runner=runner,
            meeting_id=meeting_id,
            run_id=run_id,
            config=config,
            user_task=user_task,
            start_round=1,
        )
    )
    print(json.dumps({"meeting_id": meeting_id, "run_id": run_id, "result": result}, indent=2))
    return 0


# cmd_resume: CLI handler to resume a paused run.
def cmd_resume(args: argparse.Namespace) -> int:
    # Resume a paused run with answers.
    storage = StorageRepo(Path(args.db))
    runner = create_runner()
    run = storage.get_run(args.run_id)
    if not run:
        raise SystemExit("run not found")
    config = json.loads(run["config_json"])
    events = storage.list_events(args.run_id)
    expected = find_last_pause_token(events)
    resume_payload = _load_json(Path(args.answers))
    resume_token = resume_payload.get("resume_token")
    if not resume_token:
        raise SystemExit("resume_token is required")
    if expected and resume_token != expected:
        raise SystemExit("invalid resume token")
    resume_event = make_resume_event(args.run_id, resume_token, resume_payload.get("answers", {}))
    storage.append_event_dict(
        {
            "type": resume_event.type,
            "run_id": resume_event.run_id,
            "ts_ms": resume_event.ts_ms,
            "actor": resume_event.actor,
            "payload": {**resume_event.payload, "event_code": "RESUMED"},
        }
    )
    start_round = next_round_from_events(events)
    storage.set_run_status(args.run_id, "RUNNING")
    user_task = _build_user_task(config)
    result = asyncio.run(
        run_meeting(
            storage=storage,
            runner=runner,
            meeting_id=run["meeting_id"],
            run_id=args.run_id,
            config=config,
            user_task=user_task,
            start_round=start_round,
        )
    )
    print(json.dumps({"run_id": args.run_id, "result": result}, indent=2))
    return 0


# cmd_replay: CLI handler to replay events.
def cmd_replay(args: argparse.Namespace) -> int:
    # Print stored events for a run.
    storage = StorageRepo(Path(args.db))
    events = storage.list_events(args.run_id)
    print(json.dumps({"run_id": args.run_id, "events": events}, indent=2))
    return 0


# main: CLI router.
def main() -> int:
    # CLI router.
    parser = argparse.ArgumentParser(prog="run_meeting")
    parser.add_argument("--db", default="meeting.db")

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_cmd = subparsers.add_parser("run")
    run_cmd.add_argument("--config", required=True)
    run_cmd.set_defaults(func=cmd_run)

    resume_cmd = subparsers.add_parser("resume")
    resume_cmd.add_argument("--run-id", required=True)
    resume_cmd.add_argument("--answers", required=True)
    resume_cmd.set_defaults(func=cmd_resume)

    replay_cmd = subparsers.add_parser("replay")
    replay_cmd.add_argument("--run-id", required=True)
    replay_cmd.set_defaults(func=cmd_replay)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
