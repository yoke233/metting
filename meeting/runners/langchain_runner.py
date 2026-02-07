"""Runner implementations: stub and LangChain-backed chat."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, AsyncIterator, List

from meeting.domain.models import Event, ExecutionContext, Message

try:
    from langchain_core.messages import (
        AIMessage,
        AIMessageChunk,
        BaseMessage,
        HumanMessage,
        SystemMessage,
    )
    from langchain_openai import ChatOpenAI

    _LC_AVAILABLE = True
except Exception:
    _LC_AVAILABLE = False


def _load_dotenv_if_available() -> None:
    # Load .env if python-dotenv is installed.
    try:
        from dotenv import load_dotenv
    except Exception:  # pragma: no cover
        return
    load_dotenv()


def _now_ms() -> int:
    # Millisecond timestamp for event payloads.
    import time

    return int(time.time() * 1000)


def _build_prompt(ctx: ExecutionContext) -> List[BaseMessage]:
    # Build a minimal system + user prompt for the selected speaker.
    try:
        history_limit = max(1, int(ctx.limits.get("history_max_messages", 6)))
    except (TypeError, ValueError):
        history_limit = 6
    history = "\n".join(
        f"{m.name or m.role}: {m.content}" for m in ctx.public_messages[-history_limit:]
    )
    system_text = ctx.system_instructions or f"你是{ctx.speaker}。"
    memory_text = ""
    if ctx.context_mode == "layered" and ctx.private_memory:
        memory_text = f"私有记忆:\n{json.dumps(ctx.private_memory, ensure_ascii=False)}\n\n"
    user_text = (
        f"公共摘要:\n{history}\n\n"
        f"{memory_text}"
        f"任务:\n{ctx.user_task}\n\n"
        f"请以{ctx.speaker}身份作答。"
    ).strip()
    return [SystemMessage(content=system_text), HumanMessage(content=user_text)]


def _chunk_text(chunk: Any) -> str:
    # Normalize streaming chunks into plain text.
    if isinstance(chunk, AIMessageChunk):
        content = chunk.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(item) for item in content)
    if isinstance(chunk, AIMessage):
        return str(chunk.content)
    if hasattr(chunk, "content"):
        return str(chunk.content)
    return str(chunk)


def _normalize_base_url(base_url: str) -> str:
    # Most OpenAI-compatible gateways expect a /v1 suffix.
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


class StubGroupChatRunner:
    async def run(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        # Deterministic placeholder runner for local/dev.
        message_id = f"msg-{uuid.uuid4().hex}"
        tokens = ["正在", "思考", "方案..."]
        for token in tokens:
            yield Event(
                type="token",
                run_id=ctx.run_id,
                ts_ms=_now_ms(),
                actor=f"agent:{ctx.speaker}",
                payload={"text": token, "message_id": message_id, "role": ctx.speaker},
            )
            await asyncio.sleep(0)

        message = Message(
            role="assistant",
            content=f"[{ctx.speaker}] 回复: {ctx.user_task}",
            name=ctx.speaker,
            ts_ms=_now_ms(),
            meta=None,
        )
        yield Event(
            type="agent_message",
            run_id=ctx.run_id,
            ts_ms=_now_ms(),
            actor=f"agent:{ctx.speaker}",
            payload={
                "message": {
                    "role": message.role,
                    "content": message.content,
                    "name": message.name,
                    "ts_ms": message.ts_ms,
                    "meta": message.meta,
                },
                "message_id": message_id,
                "round": ctx.round,
            },
        )


class LangChainGroupChatRunner:
    def __init__(self) -> None:
        if not _LC_AVAILABLE:
            raise RuntimeError("langchain-openai is not installed")
        # Allow local .env without explicit export.
        _load_dotenv_if_available()

        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("MEETING_OPENAI_API_KEY")
        base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("MEETING_OPENAI_BASE_URL")
        )
        model_id = (
            os.getenv("OPENAI_CHAT_MODEL_ID")
            or os.getenv("OPENAI_MODEL_ID")
            or os.getenv("MEETING_OPENAI_MODEL_ID")
            or "gpt-4o-mini"
        )
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        kwargs: dict[str, Any] = {
            "model": model_id,
            "api_key": api_key,
            "temperature": 0.2,
        }
        if base_url:
            kwargs["base_url"] = _normalize_base_url(base_url)
        self._model = ChatOpenAI(**kwargs)

    # run: execute a single speaker turn via LangChain.
    async def run(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        message_id = f"msg-{uuid.uuid4().hex}"
        prompt = _build_prompt(ctx)
        content_parts: List[str] = []

        try:
            # Stream tokens when available.
            async for chunk in self._model.astream(prompt):
                text = _chunk_text(chunk)
                if not text:
                    continue
                content_parts.append(text)
                yield Event(
                    type="token",
                    run_id=ctx.run_id,
                    ts_ms=_now_ms(),
                    actor=f"agent:{ctx.speaker}",
                    payload={"text": text, "message_id": message_id, "role": ctx.speaker},
                )
        except Exception:
            content_parts = []

        try:
            # Fallback to non-streaming call if stream failed or returned nothing.
            if content_parts:
                final_text = "".join(content_parts).strip()
            else:
                response = await self._model.ainvoke(prompt)
                final_text = _chunk_text(response).strip()
        except Exception as exc:
            raise RuntimeError(
                "LangChain call failed. Check OPENAI_API_KEY and OPENAI_BASE_URL "
                "(should include /v1 for most OpenAI-compatible services)."
            ) from exc

        message = Message(
            role="assistant",
            content=final_text,
            name=ctx.speaker,
            ts_ms=_now_ms(),
            meta=None,
        )
        yield Event(
            type="agent_message",
            run_id=ctx.run_id,
            ts_ms=_now_ms(),
            actor=f"agent:{ctx.speaker}",
            payload={
                "message": {
                    "role": message.role,
                    "content": message.content,
                    "name": message.name,
                    "ts_ms": message.ts_ms,
                    "meta": message.meta,
                },
                "message_id": message_id,
                "round": ctx.round,
            },
        )


# create_runner: select stub vs. langchain runner.
def create_runner() -> object:
    mode = os.getenv("MEETING_RUNNER", "langchain").lower()
    if mode in {"stub", "fake"}:
        return StubGroupChatRunner()
    if not _LC_AVAILABLE:
        raise RuntimeError("langchain-openai is not installed")
    return LangChainGroupChatRunner()
