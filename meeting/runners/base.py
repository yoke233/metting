"""Runner interface for pluggable agent backends."""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from meeting.domain.models import Event, ExecutionContext


class RoleRunner(Protocol):
    # Implementations should stream Event objects for a given context.
    async def run(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        ...
