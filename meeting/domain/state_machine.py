"""Meeting state machine and orchestration loop."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from .artifacts import (
    generate_adr,
    generate_flowchart,
    generate_risks,
    generate_tasks,
    parse_recorder_output,
    parse_round_summary_output,
    validate_consensus,
    validate_adr,
    validate_risks,
    validate_tasks,
)
from .context_builder import build_layered_context, build_shared_context
from meeting.config import (
    get_round_summary_prompt,
    get_recorder_output_prompt,
    get_role_output_prompt,
    get_role_prompts,
    get_role_repair_prompt,
    get_system_prompt,
)
from .models import Message, ValidationError
from .pause_resume import make_pause_event
from .termination import TerminationConfig, should_stop, metrics
from .validators import parse_and_validate_role_output


def _now_ms() -> int:
    # Millisecond timestamp for events.
    import time

    return int(time.time() * 1000)


def _message_from_dict(data: Dict[str, Any]) -> Message:
    # Convert dict payloads into Message objects.
    return Message(
        role=data.get("role", "assistant"),
        content=data.get("content", ""),
        name=data.get("name"),
        ts_ms=data.get("ts_ms"),
        meta=data.get("meta"),
    )


def _public_messages_from_events(events: List[Dict[str, Any]]) -> List[Message]:
    # Build the shared context from stored events.
    messages: List[Message] = []
    for event in events:
        if event.get("type") == "agent_message":
            payload = event.get("payload", {})
            msg = payload.get("message")
            if isinstance(msg, dict):
                messages.append(_message_from_dict(msg))
        if event.get("type") == "resume":
            payload = event.get("payload", {})
            answers = payload.get("answers", {})
            # Capture resume answers as user-visible context.
            messages.append(
                Message(
                    role="user",
                    content=f"resume answers: {answers}",
                    name="user",
                    ts_ms=event.get("ts_ms"),
                    meta=None,
                )
            )
    return messages


def _event_dict(
    event_type: str,
    run_id: str,
    actor: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    # Standardize event dicts written to storage.
    event_payload = dict(payload)
    if "event_code" not in event_payload:
        event_payload["event_code"] = _event_code_for_event(event_type, event_payload, actor)
    return {
        "type": event_type,
        "run_id": run_id,
        "ts_ms": _now_ms(),
        "actor": actor,
        "payload": event_payload,
    }


def _select_speaker(roles: List[str], round_index: int) -> str:
    # Round-robin speaker selection.
    if not roles:
        return "Speaker"
    return roles[(round_index - 1) % len(roles)]


def _event_code_for_event(event_type: str, payload: Dict[str, Any], actor: str) -> str:
    # Map internal event types to PRD-friendly event codes.
    if event_type == "agent_message":
        role = payload.get("message", {}).get("role")
        if actor == "user" or role == "user":
            return "USER_MESSAGE_ADDED"
        return "AGENT_OUTPUT"
    mapping = {
        "round_started": "ROUND_STARTED",
        "speaker_selected": "SPEAKER_SELECTED",
        "token": "AGENT_TOKEN",
        "summary_written": "SUMMARY_WRITTEN",
        "artifact_written": "ARTIFACT_WRITTEN",
        "pause": "PAUSED",
        "resume": "RESUMED",
        "metric": "METRIC_EMITTED",
        "error": "ERROR",
        "finished": "MEETING_FINISHED",
    }
    return mapping.get(event_type, event_type.upper())


def _attach_event_code(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure payload has event_code for downstream tooling.
    payload = event_dict.get("payload") or {}
    if "event_code" not in payload:
        payload = dict(payload)
        payload["event_code"] = _event_code_for_event(
            event_dict.get("type", ""),
            payload,
            event_dict.get("actor", ""),
        )
        event_dict["payload"] = payload
    return event_dict


def _compute_convergence(latest_outputs: Dict[str, Dict[str, Any]]) -> tuple[int, int]:
    # Compute open questions and disagreements from latest role outputs.
    if not latest_outputs:
        return 0, 0
    open_questions = 0
    decisions: set[str] = set()
    for output in latest_outputs.values():
        questions = output.get("questions", [])
        if isinstance(questions, list):
            open_questions += len(questions)
        decision = output.get("decision_recommendation")
        if decision:
            decisions.add(str(decision).strip().lower())
    disagreements = max(0, len(decisions) - 1)
    return open_questions, disagreements


def _compute_consensus(outputs: Dict[str, Dict[str, Any]]) -> tuple[Dict[str, int], str, float]:
    # Compute majority vote consensus from role outputs.
    votes: Dict[str, int] = {}
    for output in outputs.values():
        decision = output.get("decision_recommendation")
        if not decision:
            continue
        key = str(decision).strip()
        if not key:
            continue
        votes[key] = votes.get(key, 0) + 1
    if not votes:
        return {}, "", 0.0
    ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    winner = ranked[0][0]
    total = sum(votes.values())
    consensus_score = votes[winner] / total if total else 0.0
    return votes, winner, consensus_score


def _summary_to_message(summary: Dict[str, Any]) -> Message:
    # Convert summary dict into a public Message for layered context.
    text = json.dumps(summary, ensure_ascii=False)
    return Message(role="system", content=f"round_summary: {text}", name="summary")


def _summaries_to_messages(
    summaries: List[Dict[str, Any]],
    keep_last: int,
) -> List[Message]:
    # Convert latest summaries into Messages.
    if keep_last <= 0:
        return []
    trimmed = summaries[-keep_last:]
    return [_summary_to_message(summary) for summary in trimmed]


def _normalize_memory(memory: Dict[str, Any] | None) -> Dict[str, Any]:
    # Ensure memory has all required lists.
    base = {
        "assumptions": [],
        "notes": [],
        "pending_checks": [],
        "risks_pool": [],
        "drafts": [],
    }
    if not memory:
        return base
    merged = dict(base)
    for key in base:
        value = memory.get(key)
        if isinstance(value, list):
            merged[key] = value
    return merged


def _trim_list(items: List[Any], max_items: int) -> List[Any]:
    # Trim a list to the latest N items.
    if max_items <= 0:
        return []
    if len(items) <= max_items:
        return items
    return items[-max_items:]


def _merge_memory(
    memory: Dict[str, Any] | None,
    role_output: Dict[str, Any],
    max_items: int,
) -> Dict[str, Any]:
    # Merge role output into private memory snapshot.
    merged = _normalize_memory(memory)
    merged["assumptions"] += role_output.get("assumptions", [])
    merged["pending_checks"] += role_output.get("questions", [])
    merged["risks_pool"] += role_output.get("risks", [])
    proposal = role_output.get("proposal")
    if proposal:
        merged["drafts"].append(str(proposal))
    decision = role_output.get("decision_recommendation")
    if decision:
        merged["notes"].append(str(decision))
    for tradeoff in role_output.get("tradeoffs", []):
        if tradeoff:
            merged["notes"].append(str(tradeoff))
    for key in merged:
        merged[key] = _trim_list(merged[key], max_items)
    return merged


async def _run_speaker_turn(
    storage,
    runner,
    meeting_id: str,
    run_id: str,
    round_index: int,
    speaker: str,
    public_messages: List[Message],
    summary_messages: List[Message],
    private_memory: Dict[str, Any],
    system_text: str,
    user_task: str,
    limits: Dict[str, Any],
    context_mode: str = "shared",
    capture_public: bool = True,
) -> tuple[str | None, Dict[str, Any] | None]:
    # Execute a single speaker turn and persist streamed events.
    if context_mode == "layered":
        ctx = build_layered_context(
            meeting_id=meeting_id,
            run_id=run_id,
            round_index=round_index,
            speaker=speaker,
            summary_messages=summary_messages,
            private_memory=private_memory,
            system_instructions=system_text,
            user_task=user_task,
            limits=limits,
        )
    else:
        ctx = build_shared_context(
            meeting_id=meeting_id,
            run_id=run_id,
            round_index=round_index,
            speaker=speaker,
            public_messages=public_messages,
            system_instructions=system_text,
            user_task=user_task,
            limits=limits,
        )

    last_message: str | None = None
    parsed_output: Dict[str, Any] | None = None
    async for event in runner.run(ctx):
        event_dict = {
            "type": event.type,
            "run_id": event.run_id,
            "ts_ms": event.ts_ms,
            "actor": event.actor,
            "payload": event.payload,
        }
        storage.append_event_dict(_attach_event_code(event_dict))
        if event.type == "agent_message":
            msg = event.payload.get("message")
            if isinstance(msg, dict):
                if capture_public:
                    public_messages.append(_message_from_dict(msg))
                last_message = str(msg.get("content", ""))
    try:
        if last_message and limits.get("validate_role_output"):
            parsed_output = parse_and_validate_role_output(last_message)
    except ValidationError as exc:
        storage.append_event_dict(
            _event_dict(
                "error",
                run_id,
                "validator",
                {
                    "message": str(exc),
                    "stage": "role_output_validation",
                    "speaker": speaker,
                },
            )
        )
        if limits.get("role_repair_prompt"):
            repair_prompt = str(limits.get("role_repair_prompt", "")).strip()
        else:
            repair_prompt = ""
        if repair_prompt:
            repair_system_text = "\n".join([system_text, repair_prompt]).strip()
            repair_user_task = (
                f"{user_task}\n\n请将以下输出修复为严格 JSON：\n{last_message}"
            )
            limits_retry = dict(limits)
            limits_retry["validate_role_output"] = True
            limits_retry["role_repair_prompt"] = ""
            return await _run_speaker_turn(
                storage=storage,
                runner=runner,
                meeting_id=meeting_id,
                run_id=run_id,
                round_index=round_index,
                speaker=speaker,
                public_messages=public_messages,
                summary_messages=summary_messages,
                private_memory=private_memory,
                system_text=repair_system_text,
                user_task=repair_user_task,
                limits=limits_retry,
                context_mode=context_mode,
                capture_public=capture_public,
            )
    return last_message, parsed_output


# run_meeting: orchestrate rounds, persist events, and generate artifacts.
async def run_meeting(
    storage,
    runner,
    meeting_id: str,
    run_id: str,
    config: Dict[str, Any],
    user_task: str,
    start_round: int = 1,
) -> Dict[str, Any]:
    # Main orchestration loop: select speaker, run, persist events, evaluate stop.
    roles = config.get("roles", [])
    max_rounds = int(config.get("max_rounds", 6))
    role_prompts = config.get("role_prompts") or get_role_prompts()
    system_prompt = get_system_prompt()
    role_output_prompt = get_role_output_prompt()
    role_repair_prompt = get_role_repair_prompt()
    round_summary_prompt = get_round_summary_prompt()
    context_mode = str(config.get("context_mode", "shared")).lower()
    parallel_mode = bool(config.get("parallel_mode", False))
    default_min_rounds = min(len(roles), max_rounds) if roles else 1
    termination_cfg = TerminationConfig(
        max_rounds=max_rounds,
        min_rounds=int(config.get("termination", {}).get("min_rounds", default_min_rounds)),
        open_questions_max=int(config.get("termination", {}).get("open_questions_max", 2)),
        disagreements_max=int(config.get("termination", {}).get("disagreements_max", 1)),
    )

    # Resume from existing events if any.
    events = storage.list_events(run_id)
    public_messages = _public_messages_from_events(events)
    limits_base = dict(config.get("limits", {}))
    if "roles" not in limits_base:
        limits_base["roles"] = roles
    limits_base.setdefault("validate_role_output", True)
    limits_base.setdefault("role_repair_prompt", role_repair_prompt)
    last_round = start_round - 1
    latest_role_outputs: Dict[str, Dict[str, Any]] = {}
    summary_keep_last = int(config.get("summary_keep_last", 3))
    memory_max_items = int(config.get("memory_max_items", 50))
    summary_history: List[Dict[str, Any]] = []
    if context_mode == "layered":
        stored = storage.list_summaries(run_id)
        summary_history = [item["content"] for item in stored if "content" in item]
    summary_messages = _summaries_to_messages(summary_history, summary_keep_last)

    for round_index in range(start_round, max_rounds + 1):
        round_outputs: Dict[str, Dict[str, Any]] = {}
        speakers = [role for role in roles if str(role).lower() != "recorder"]
        if not speakers:
            speakers = [_select_speaker(roles, round_index)]
        if not parallel_mode:
            speakers = [_select_speaker(roles, round_index)]
        last_round = round_index

        # Record round start and speaker selection.
        storage.append_event_dict(
            _event_dict(
                "round_started",
                run_id,
                "orchestrator",
                {"round": round_index, "mode": "parallel" if parallel_mode else "sequential"},
            )
        )
        storage.append_event_dict(
            _event_dict(
                "speaker_selected",
                run_id,
                "orchestrator",
                {
                    "speaker": speakers[0] if len(speakers) == 1 else None,
                    "speakers": speakers,
                    "round": round_index,
                    "strategy": "parallel_all" if parallel_mode else "round_robin",
                },
            )
        )

        async def _run_role(role_name: str):
            role_text = role_prompts.get(role_name, f"你是{role_name}。")
            system_text = f"{system_prompt}\n{role_text}".strip() if system_prompt else role_text
            limits = dict(limits_base)
            if role_name.lower() != "recorder" and role_output_prompt:
                system_text = "\n".join([system_text, role_output_prompt]).strip()
            if role_name.lower() == "recorder":
                limits["validate_role_output"] = False

            private_memory = {}
            if context_mode == "layered":
                stored_memory = storage.get_memory(run_id, role_name)
                private_memory = _normalize_memory(stored_memory)

            return await _run_speaker_turn(
                storage=storage,
                runner=runner,
                meeting_id=meeting_id,
                run_id=run_id,
                round_index=round_index,
                speaker=role_name,
                public_messages=public_messages,
                summary_messages=summary_messages,
                private_memory=private_memory,
                system_text=system_text,
                user_task=user_task,
                limits=limits,
                context_mode=context_mode,
            )

        if parallel_mode and len(speakers) > 1:
            results = await asyncio.gather(*[_run_role(s) for s in speakers])
            for role_name, result in zip(speakers, results):
                _, parsed_output = result
                if parsed_output:
                    latest_role_outputs[role_name] = parsed_output
                    round_outputs[role_name] = parsed_output
                    if context_mode == "layered" and role_name.lower() != "recorder":
                        stored_memory = storage.get_memory(run_id, role_name)
                        private_memory = _normalize_memory(stored_memory)
                        updated_memory = _merge_memory(private_memory, parsed_output, memory_max_items)
                        storage.upsert_memory(run_id, role_name, updated_memory)
        else:
            role_name = speakers[0]
            _, parsed_output = await _run_role(role_name)
            if parsed_output:
                latest_role_outputs[role_name] = parsed_output
                round_outputs[role_name] = parsed_output
                if context_mode == "layered" and role_name.lower() != "recorder":
                    stored_memory = storage.get_memory(run_id, role_name)
                    private_memory = _normalize_memory(stored_memory)
                    updated_memory = _merge_memory(private_memory, parsed_output, memory_max_items)
                    storage.upsert_memory(run_id, role_name, updated_memory)

        # Optional pause hook for demo/testing.
        pause_on_round = config.get("pause_on_round")
        if pause_on_round and int(pause_on_round) == round_index:
            pause_event = make_pause_event(
                run_id=run_id,
                reason="missing_info",
                questions=[{"key": "qps", "ask": "Peak QPS?", "why": "capacity depends", "required": True}],
            )
            storage.append_event_dict(
                _attach_event_code(
                    {
                        "type": pause_event.type,
                        "run_id": pause_event.run_id,
                        "ts_ms": pause_event.ts_ms,
                        "actor": pause_event.actor,
                        "payload": pause_event.payload,
                    }
                )
            )
            storage.set_run_status(run_id, "PAUSED")
            return {"status": "PAUSED"}

        if context_mode == "layered" and round_summary_prompt:
            recorder_role_text = role_prompts.get("Recorder", "你是Recorder。")
            summary_system_text = "\n".join(
                text for text in [system_prompt, recorder_role_text, round_summary_prompt] if text
            ).strip()
            summary_limits = dict(limits_base)
            summary_limits["validate_role_output"] = False
            summary_text, _ = await _run_speaker_turn(
                storage=storage,
                runner=runner,
                meeting_id=meeting_id,
                run_id=run_id,
                round_index=round_index,
                speaker="Recorder",
                public_messages=public_messages,
                summary_messages=summary_messages,
                private_memory={},
                system_text=summary_system_text,
                user_task=f"{user_task}\n\n请总结第{round_index}轮。",
                limits=summary_limits,
                context_mode="shared",
                capture_public=False,
            )
            summary_text = summary_text or ""
            if summary_text:
                try:
                    summary = parse_round_summary_output(summary_text, round_index)
                    storage.save_artifact(run_id, "SUMMARY", "v2", summary)
                    storage.append_event_dict(
                        _event_dict(
                            "summary_written",
                            run_id,
                            "recorder",
                            {"round": round_index, "content": summary},
                        )
                    )
                    summary_history.append(summary)
                    summary_messages = _summaries_to_messages(summary_history, summary_keep_last)
                except Exception as exc:
                    storage.append_event_dict(
                        _event_dict(
                            "error",
                            run_id,
                            "recorder",
                            {"message": str(exc), "stage": "round_summary"},
                        )
                    )

        consensus_score = None
        vote_counts = None
        if parallel_mode:
            vote_counts, winner, consensus_score = _compute_consensus(round_outputs)
            consensus = {
                "round": round_index,
                "votes": vote_counts,
                "winner": winner,
                "rationale": "多数票收敛" if winner else "无有效投票",
            }
            validate_consensus(consensus)
            storage.save_artifact(run_id, "CONSENSUS", "v1", consensus)
            storage.append_event_dict(
                _event_dict(
                    "artifact_written",
                    run_id,
                    "orchestrator",
                    {"artifact_type": "CONSENSUS", "version": "v1", "content": consensus},
                )
            )

        # Stop decision based on thresholds and observed convergence.
        artifacts_valid = False
        open_questions, disagreements = _compute_convergence(latest_role_outputs)
        if not latest_role_outputs:
            open_questions = termination_cfg.open_questions_max + 1
            disagreements = termination_cfg.disagreements_max + 1
        storage.append_event_dict(
            _event_dict(
                "metric",
                run_id,
                "system",
                metrics(open_questions, disagreements, consensus_score, vote_counts),
            )
        )

        if should_stop(round_index, artifacts_valid, open_questions, disagreements, termination_cfg):
            break

    # Generate artifacts after discussion rounds finish.
    recorder_prompt = get_recorder_output_prompt()
    recorder_role_text = role_prompts.get("Recorder", "你是Recorder。")
    recorder_system_text = "\n".join(
        text for text in [system_prompt, recorder_role_text, recorder_prompt] if text
    ).strip()
    recorder_limits = dict(limits_base)
    recorder_limits["validate_role_output"] = False
    if "history_max_messages" not in recorder_limits:
        try:
            recorder_limits["history_max_messages"] = int(
                config.get("recorder_history_max_messages", 20)
            )
        except (TypeError, ValueError):
            recorder_limits["history_max_messages"] = 20

    recorder_text, _ = await _run_speaker_turn(
        storage=storage,
        runner=runner,
        meeting_id=meeting_id,
        run_id=run_id,
        round_index=last_round + 1,
        speaker="Recorder",
        public_messages=public_messages,
        summary_messages=summary_messages,
        private_memory={},
        system_text=recorder_system_text,
        user_task=user_task,
        limits=recorder_limits,
        context_mode="shared",
        capture_public=False,
    )
    recorder_text = recorder_text or ""

    if recorder_text:
        storage.save_artifact(run_id, "SUMMARY", "v1", {"text": recorder_text})
        storage.append_event_dict(
            _event_dict("summary_written", run_id, "recorder", {"content": recorder_text})
        )

    try:
        parsed = parse_recorder_output(recorder_text)
        adr = parsed["ADR"]
        tasks = parsed["TASKS"]
        risks = parsed["RISKS"]
    except Exception as exc:
        storage.append_event_dict(
            _event_dict("error", run_id, "recorder", {"message": str(exc)})
        )
        adr = generate_adr([m.content for m in public_messages], user_task)
        tasks = generate_tasks()
        risks = generate_risks()

    validate_adr(adr)
    validate_tasks(tasks)
    validate_risks(risks)

    storage.save_artifact(run_id, "ADR", "v1", adr)
    storage.save_artifact(run_id, "TASKS", "v1", tasks)
    storage.save_artifact(run_id, "RISKS", "v1", risks)
    flowchart = generate_flowchart(roles, last_round)
    storage.save_artifact(run_id, "FLOWCHART", "v1", flowchart)

    storage.append_event_dict(
        _event_dict(
            "artifact_written",
            run_id,
            "recorder",
            {"artifact_type": "ADR", "version": "v1", "content": adr},
        )
    )
    storage.append_event_dict(
        _event_dict(
            "artifact_written",
            run_id,
            "recorder",
            {"artifact_type": "TASKS", "version": "v1", "content": tasks},
        )
    )
    storage.append_event_dict(
        _event_dict(
            "artifact_written",
            run_id,
            "recorder",
            {"artifact_type": "RISKS", "version": "v1", "content": risks},
        )
    )
    storage.append_event_dict(
        _event_dict(
            "artifact_written",
            run_id,
            "recorder",
            {"artifact_type": "FLOWCHART", "version": "v1", "content": flowchart},
        )
    )

    # Mark run as completed.
    storage.set_run_status(run_id, "DONE")
    return {
        "status": "DONE",
        "artifacts": {"ADR": adr, "TASKS": tasks, "RISKS": risks, "FLOWCHART": flowchart},
    }


# next_round_from_events: compute resume start round.
def next_round_from_events(events: List[Dict[str, Any]]) -> int:
    # Find the next round index for resume.
    rounds = [e.get("payload", {}).get("round") for e in events if e.get("type") == "round_started"]
    rounds = [r for r in rounds if isinstance(r, int)]
    if not rounds:
        return 1
    return max(rounds) + 1
