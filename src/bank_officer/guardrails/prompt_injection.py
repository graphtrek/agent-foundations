"""Before-model guardrail: block prompt-injection / instruction-override attempts."""

import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all|the|your) (previous|prior|above) (instructions|rules)",
        r"disregard (all|the|your) (previous|prior|above) (instructions|rules)",
        r"reveal (your|the) (system|hidden) prompt",
        r"you are now (a|an)",
        r"\bjailbreak\b",
        r"\bdan mode\b",
        r"hagyd figyelmen kívül (az|a)? ?(előző|korábbi) utasítás",
        r"(áruld el|írd ki) a (rendszer|system) ?promptot",
        r"mostantól (te|ön) (egy|vagy)",
    )
]

INJECTION_REFUSAL = (
    "I can't follow instructions embedded in a message like that. Please ask "
    "a normal question about the selected customer's accounts, transactions, "
    "products, or offers."
)


def is_prompt_injection(text: str) -> bool:
    """Deterministic instruction-override / prompt-extraction check, shared by
    the middleware below and the non-LLM endpoint router."""
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


class PromptInjectionGuardMiddleware(AgentMiddleware):
    """Block messages that try to override instructions or extract the prompt."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
        )
        if last_human is not None and is_prompt_injection(str(last_human.content)):
            return {"messages": [AIMessage(content=INJECTION_REFUSAL)], "jump_to": "end"}
        return None
