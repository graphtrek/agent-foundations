"""In-process registry of chat turns being generated right now.

A turn publishes every SSE-style event (``route``, ``tool_call``,
``tool_result``, ``customer``, ``reply``, ``app_error``) to its ``LiveRun``.
A browser following the chat (``GET /api/chats/{id}/live``) replays the
events so far, then follows new ones until the run ends - so a viewer that
reconnects or arrives late never affects the run itself. Same pattern as the
dev-vault chat service's ``chat.live``.

Plain module-level state: run the web app with a single uvicorn worker.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LiveRun:
    chat_id: str
    prompt: str  # the officer's message shown above the live reply
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    done: bool = False
    _waiters: list[asyncio.Future[None]] = field(default_factory=list, repr=False)

    def emit(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.events.append((event, data or {}))
        self._wake()

    def finish(self) -> None:
        self.done = True
        self._wake()

    def _wake(self) -> None:
        waiters, self._waiters = self._waiters, []
        for fut in waiters:
            if not fut.done():
                fut.set_result(None)

    async def follow(self) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Every event from the start, then new ones as they come, until the run ends."""
        seen = 0
        while True:
            batch = self.events[seen:]
            seen += len(batch)
            for item in batch:
                yield item
            if self.done and seen >= len(self.events):
                return
            if not batch:
                fut = asyncio.get_running_loop().create_future()
                self._waiters.append(fut)
                await fut


_runs: dict[str, LiveRun] = {}


def start(chat_id: str, prompt: str) -> LiveRun:
    run = LiveRun(chat_id=chat_id, prompt=prompt)
    _runs[chat_id] = run
    return run


def get(chat_id: str) -> LiveRun | None:
    return _runs.get(chat_id)


def drop(chat_id: str) -> None:
    _runs.pop(chat_id, None)
