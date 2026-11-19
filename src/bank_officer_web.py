"""Bank branch officer assistant - browser chat with live (SSE) progress.

The same pipeline as the terminal example (``bank_officer_agent.py``), shared
through ``utils.branch_session.BranchSession``, served over a small JSON/SSE
API modelled on the dev-vault chat service:

- ``POST /api/chats/{id}/messages`` starts the turn as a background task
  (the agent pipeline is synchronous, so it runs in a worker thread) and
  returns at once.
- ``GET /api/chats/{id}/live`` follows it over Server-Sent Events: it
  replays the events so far, then streams new ones - the endpoint router's
  match (``route``), each coordinator tool call and its redacted result
  (``tool_call``/``tool_result``), a customer switch (``customer``) and the
  guardrail-checked reply (``reply``). Closing the stream never stops the
  turn; reopening the page re-attaches.
- ``POST /api/chats/{id}/cancel`` stops the turn after its current step and
  starts a fresh coordinator thread, so a half-finished turn never lingers
  in the model's context.
- ``DELETE /api/chats/{id}`` ends the session and saves its transcript to
  ``conversations/``.

The page itself is ``src/resources/webapp_mockup/chat.html``, served together
with ``catalog.html`` from that directory. Sessions live in process memory:
run a single worker, and a restart ends every session.

Run with: uv run python src/bank_officer_web.py   (then open http://127.0.0.1:8010/)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bank_officer_agent import CONVERSATIONS_DIR, LOGS_DIR, build_agents
from utils import live_run
from utils.branch_session import FAILURE_REPLY, BranchSession, customer_info
from utils.tools import BranchContext

MOCKUP_DIR = Path(__file__).resolve().parent / "resources" / "webapp_mockup"
LOG_FILE = LOGS_DIR / "bank_officer_web.log"
HOST = os.environ.get("BANK_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("BANK_WEB_PORT", "8010"))
MAX_MESSAGE_CHARS = 2000
logger = logging.getLogger(__name__)

endpoint_router, coordinator = build_agents()


@dataclass
class WebChat:
    session: BranchSession
    turns: list[dict[str, Any]] = field(default_factory=list)  # finished: {prompt, events}
    cancel: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[None] | None = None


_chats: dict[str, WebChat] = {}


def _get_chat(chat_id: str) -> WebChat:
    chat = _chats.get(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Unknown or ended chat session.")
    return chat


def _is_running(chat_id: str) -> bool:
    run = live_run.get(chat_id)
    return run is not None and not run.done


class PostMessageRequest(BaseModel):
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


app = FastAPI(title="Bank Branch Officer Chat")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/chat.html")


@app.post("/api/chats", status_code=201)
def new_chat() -> dict[str, str]:
    chat_id = uuid.uuid4().hex[:12]
    session = BranchSession(
        endpoint_router,
        coordinator,
        BranchContext(officer_id="officer-demo", branch_id="branch-buda"),
        thread_id_prefix=f"web-{chat_id}",
    )
    _chats[chat_id] = WebChat(session=session)
    return {"chat_id": chat_id}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str) -> dict[str, Any]:
    chat = _get_chat(chat_id)
    run = live_run.get(chat_id)
    return {
        "customer": customer_info(chat.session.current_customer_id),
        "turns": chat.turns,
        "live": {"prompt": run.prompt} if run is not None and not run.done else None,
    }


@app.delete("/api/chats/{chat_id}")
def end_chat(chat_id: str) -> dict[str, str | None]:
    chat = _get_chat(chat_id)
    if _is_running(chat_id):
        raise HTTPException(status_code=409, detail="Stop the running reply first.")
    del _chats[chat_id]
    path = chat.session.save(CONVERSATIONS_DIR)
    if path is not None:
        logger.info("Conversation saved to %s", path)
    return {"saved": str(path) if path else None}


def _run_turn(chat: WebChat, prompt: str, run: live_run.LiveRun, loop: asyncio.AbstractEventLoop) -> list:
    """Worker thread: run the synchronous pipeline, forwarding each event to
    the LiveRun on the event loop. Returns the events for the chat history."""
    events: list[tuple[str, dict[str, Any]]] = []

    def emit(event: str, data: dict[str, Any]) -> None:
        events.append((event, data))
        loop.call_soon_threadsafe(run.emit, event, data)

    stream = chat.session.stream_turn(prompt)
    try:
        for event, data in stream:
            if chat.cancel.is_set():
                break
            emit(event, data)
        else:
            return events
    except Exception:  # stream_turn already falls back; this is a last resort
        logger.exception("Turn failed")
        emit("app_error", {"message": FAILURE_REPLY})
        return events
    finally:
        stream.close()
    # Cancelled mid-turn: drop the possibly half-written coordinator thread.
    chat.session.reset_thread()
    emit("stopped", {})
    return events


@app.post("/api/chats/{chat_id}/messages", status_code=202)
async def post_message(chat_id: str, req: PostMessageRequest) -> dict[str, bool]:
    chat = _get_chat(chat_id)
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty message.")
    if _is_running(chat_id):
        raise HTTPException(status_code=409, detail="The previous message is still being answered.")

    run = live_run.start(chat_id, content)
    chat.cancel.clear()
    loop = asyncio.get_running_loop()

    async def turn() -> None:
        events: list = []
        try:
            events = await asyncio.to_thread(_run_turn, chat, content, run, loop)
        finally:
            chat.turns.append({"prompt": content, "events": events})
            run.finish()
            live_run.drop(chat_id)
            chat.task = None

    chat.task = asyncio.create_task(turn())
    return {"accepted": True}


@app.post("/api/chats/{chat_id}/cancel", status_code=204)
def cancel_reply(chat_id: str) -> Response:
    chat = _get_chat(chat_id)
    if not _is_running(chat_id):
        raise HTTPException(status_code=404, detail="No running reply for this chat.")
    chat.cancel.set()
    return Response(status_code=204)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/chats/{chat_id}/live")
async def stream_live(chat_id: str) -> StreamingResponse:
    _get_chat(chat_id)
    run = live_run.get(chat_id)

    async def events():
        if run is not None:
            async for event, data in run.follow():
                yield _sse(event, data)
        yield _sse("done", {})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)


# Last, so the API routes above take precedence: catalog.html and chat.html.
app.mount("/", StaticFiles(directory=MOCKUP_DIR), name="mockup")


if __name__ == "__main__":
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    print(f"Bank Branch Officer web chat: http://{HOST}:{PORT}/")
    uvicorn.run(app, host=HOST, port=PORT, workers=1)
