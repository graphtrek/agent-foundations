"""One bank branch officer chat session, shared by the CLI and the web chat.

``BranchSession.stream_turn()`` runs a single officer turn and yields
progress events as they happen, so ``terminal.py`` and
``main.py`` (browser, over SSE) run the exact same pipeline:

1. The endpoint router (Jev decision model) matches the question to a
   catalog endpoint - ``route`` event. A router failure fails closed.
2. Code-level entitlement short-circuit: a denied endpoint never reaches the
   coordinator.
3. The coordinator runs, streamed with LangGraph ``stream_mode="updates"`` -
   ``tool_call`` / ``tool_result`` events for its tools (customer lookup and
   the two specialists) as each one starts and finishes.
4. The final reply goes through ``_deliver()``, the deterministic response
   gateway (no LLM) - ``reply`` event.

The reply text is emitted only once the coordinator has finished, never as
raw model tokens: the guardrail middleware (``PIIMiddleware`` output
redaction, the query-only ``after_model`` rewrite) acts on the finished
model message, so streaming tokens would show the officer text the
guardrails later redact or rewrite. Tool-result previews are passed through
``redact_pii()`` for the same reason.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from data import bank_data
from guardrails.endpoint_access import access_denied_reply
from guardrails.pii import redact_pii
from localization.language import AUTO, normalize, resolve_language, set_current_language
from localization.messages import text
from routing.decision_router import EndpointRouter, EndpointRouterError
from session.conversation_util import message_text, save_conversation
from tools.branch_context import BranchContext

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 80
PREVIEW_CHARS = 600
REASON_CHARS = 500

Event = tuple[str, dict[str, Any]]


def _update_messages(update: Any) -> list[Any]:
    """Messages carried by one node's ``updates`` chunk (a dict, a list of
    dicts when several tools return ``Command`` updates, or ``None``)."""
    items = update if isinstance(update, list) else [update]
    messages: list[Any] = []
    for item in items:
        if isinstance(item, Command):
            item = item.update
        if isinstance(item, dict):
            messages.extend(item.get("messages") or [])
    return messages


def _reasoning(message: Any) -> str:
    """The model's stated reason for a step: provider reasoning text when the
    response carries any, else the plain text it wrote next to its tool calls."""
    extra = getattr(message, "additional_kwargs", None) or {}
    for key in ("reasoning_content", "reasoning"):
        if isinstance(extra.get(key), str) and extra[key].strip():
            return extra[key].strip()
    content = message.content
    if isinstance(content, list):
        parts = [
            block.get("reasoning") or block.get("thinking") or ""
            for block in content
            if isinstance(block, dict) and block.get("type") in ("reasoning", "thinking")
        ]
        text = "\n".join(p for p in parts if isinstance(p, str) and p.strip())
        if text:
            return text.strip()
    return message_text(content).strip() if getattr(message, "tool_calls", None) else ""


def customer_info(customer_id: str | None) -> dict[str, Any] | None:
    customer = bank_data.find_customer(customer_id) if customer_id else None
    if customer is None:
        return None
    return {
        "id": customer.customer_id,
        "name": customer.full_name,
        "tier": customer.entitlement_tier,
    }


def names_other_customer(question: str, current_customer_id: str | None) -> bool:
    """Whether the question names a customer other than the selected one.

    Hungarian suffixes ("Bencével") rule out exact matching, so each name part
    is compared by its stem (the part minus its last letter).
    """
    text = question.lower()
    for customer in bank_data.list_customers():
        if customer.customer_id == current_customer_id:
            continue
        parts = [p for p in customer.full_name.lower().split() if len(p) >= 4]
        if any(p[:-1] in text for p in parts):
            return True
    return False


class BranchSession:
    """State of one officer's conversation: selected customer, coordinator
    thread and the transcript saved to ``conversations/`` at the end."""

    def __init__(
        self,
        endpoint_router: EndpointRouter | None,
        coordinator: Any,
        context: BranchContext,
        thread_id_prefix: str = "branch-visit",
        architecture: str | None = None,
        language: str = AUTO,
    ) -> None:
        self.endpoint_router = endpoint_router
        self.coordinator = coordinator
        self.context = context
        self.thread_id_prefix = thread_id_prefix
        self.architecture = architecture
        self.language_setting = normalize(language)  # "auto" or a fixed language
        self.language: str | None = None  # language of the latest turn
        self.current_customer_id: str | None = None
        self.transcript: list[Any] = []
        self.first_prompt: str | None = None
        self._thread_number = 1
        self._thread_message_count = 0

    # -- helpers ---------------------------------------------------------

    def _deliver(
        self, reply: str, user_input: str | None = None, **extra: Any
    ) -> Event:
        """Deterministic response gateway: the only path a reply takes to the
        officer. ``user_input`` is passed only for turns the coordinator never
        saw, so the saved transcript still shows the officer's question."""
        if user_input is not None:
            self.transcript.append(HumanMessage(content=user_input))
            self.transcript.append(AIMessage(content=reply))
        return "reply", {"text": reply, "language": self.language, **extra}

    def set_language(self, language: str | None) -> None:
        """Pick the reply language: ``"auto"`` detects it on every message."""
        self.language_setting = normalize(language)

    def reset_thread(self) -> None:
        """Start a fresh coordinator thread (customer switch, cancelled turn)."""
        self._thread_number += 1
        self._thread_message_count = 0

    # -- one turn --------------------------------------------------------

    def stream_turn(self, user_input: str) -> Iterator[Event]:
        """Run one officer turn, yielding ``(event, data)`` pairs:
        ``route``, ``tool_call``, ``tool_result``, ``customer`` and finally
        exactly one ``reply``."""
        if self.first_prompt is None:
            self.first_prompt = user_input
        self.language = resolve_language(self.language_setting, user_input, self.language)
        set_current_language(self.language)
        logger.info("Officer turn: %s", user_input)
        t0 = time.perf_counter()
        mark = t0  # end of the previous pipeline step

        def now_ms() -> int:
            return round((time.perf_counter() - t0) * 1000)

        matched = None
        if self.endpoint_router is None:
            # This architecture has no router step: nothing is matched, so
            # there is no code-level short-circuit either. The entitlement
            # rule still holds in the specialist gate and the tier-restricted
            # tools.
            yield "route", {
                "endpoint": None,
                "language": self.language,
                "skipped": True,
                "at_ms": now_ms(),
                "elapsed_ms": now_ms(),
            }
        else:
            try:
                matched = self.endpoint_router.route(user_input, self.current_customer_id)
            except EndpointRouterError:
                # Fail closed: an untrusted routing result must not let the
                # question through without its entitlement check.
                logger.exception("Endpoint router failed")
                yield self._deliver(text("failure"), user_input)
                return
            if matched and names_other_customer(user_input, self.current_customer_id):
                # The officer is switching customers in this very question, so
                # the router's verdict used the previous customer's tier and is
                # stale. Leave it undecided: select_customer runs first, and the
                # specialist gate / tier-restricted tools re-check access with
                # the newly selected customer.
                matched["access_denied"] = None
            logger.info("Matched endpoint: %s", matched)
            yield "route", {
                "endpoint": matched,
                "language": self.language,
                "at_ms": now_ms(),
                "elapsed_ms": now_ms(),
            }
        mark = time.perf_counter()

        # Code-level short-circuit: a denied endpoint never reaches the
        # coordinator, so the refusal can't depend on a prompt being followed.
        if matched and matched.get("access_denied") is True:
            logger.info("Access denied by code for customer %s", self.current_customer_id)
            yield self._deliver(
                access_denied_reply(matched), user_input, at_ms=now_ms(), total_ms=now_ms()
            )
            return

        thread_config: RunnableConfig = {
            "configurable": {"thread_id": f"{self.thread_id_prefix}-{self._thread_number}"},
            "tags": ["BRANCH_OFFICER"],
            "recursion_limit": RECURSION_LIMIT,
        }
        final_state: dict[str, Any] | None = None
        try:
            for mode, chunk in self.coordinator.stream(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "matched_endpoint": matched,
                    "current_customer_id": self.current_customer_id,
                },
                config=thread_config,
                context=self.context,
                stream_mode=["updates", "values"],
            ):
                if mode == "values":
                    final_state = chunk
                    continue
                for node, update in chunk.items():
                    for message in _update_messages(update):
                        if node == "model" and isinstance(message, AIMessage):
                            llm_ms = round((time.perf_counter() - mark) * 1000)
                            mark = time.perf_counter()
                            reason = redact_pii(_reasoning(message))[:REASON_CHARS]
                            for i, call in enumerate(message.tool_calls):
                                yield "tool_call", {
                                    "id": call["id"],
                                    "name": call["name"],
                                    "args": call["args"],
                                    "at_ms": now_ms(),
                                    "llm_ms": llm_ms if i == 0 else 0,
                                    "reason": reason,
                                }
                        elif isinstance(message, ToolMessage):
                            text = redact_pii(message_text(message.content))
                            mark = time.perf_counter()
                            yield "tool_result", {
                                "at_ms": now_ms(),
                                "id": message.tool_call_id,
                                "name": message.name,
                                "ok": message.status != "error",
                                "preview": text[:PREVIEW_CHARS],
                            }
        except Exception:
            logger.exception("Coordinator failed")
            self.reset_thread()  # the thread may hold a half-finished turn
            yield self._deliver(text("failure"), user_input)
            return
        if final_state is None:
            self.reset_thread()
            yield self._deliver(text("failure"), user_input)
            return

        messages = final_state["messages"]
        self.transcript.extend(messages[self._thread_message_count :])
        self._thread_message_count = len(messages)

        new_customer_id = final_state.get("current_customer_id", self.current_customer_id)
        if new_customer_id != self.current_customer_id:
            if self.current_customer_id is not None:
                # Customer switched: a fresh coordinator thread drops the
                # previous customer's data from the model's context.
                logger.info(
                    "Customer switched %s -> %s; resetting thread",
                    self.current_customer_id,
                    new_customer_id,
                )
                self.reset_thread()
            self.current_customer_id = new_customer_id
            yield "customer", {"customer": customer_info(new_customer_id)}

        last = messages[-1]
        yield self._deliver(
            message_text(last.content),
            llm_ms=round((time.perf_counter() - mark) * 1000),
            reason=redact_pii(_reasoning(last))[:REASON_CHARS] if isinstance(last, AIMessage) else "",
            at_ms=now_ms(),
            total_ms=now_ms(),
        )

    def run_turn(self, user_input: str) -> str:
        """Run one turn without following its progress; return the reply."""
        reply = text("failure")
        for event, data in self.stream_turn(user_input):
            if event == "reply":
                reply = data["text"]
        return reply

    def save(self, conversations_dir: Path) -> Path | None:
        """Save the transcript as Markdown; ``None`` when nothing was said."""
        if not self.transcript or not self.first_prompt:
            return None
        return save_conversation(
            self.first_prompt,
            self.transcript,
            conversations_dir,
            title="Bank Branch Officer Chat Conversation",
            assistant_heading="Assistant",
        )
