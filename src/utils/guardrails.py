"""Guardrail middleware for the bank branch officer assistant.

Deterministic "before model" and "after model" checks that run around every
LLM call the example makes - the coordinator's and both specialists' (the Jev endpoint router is not a
chat model; it reuses ``is_prompt_injection()`` and ``redact_pii()``) - on
top of whatever the prompt itself says. These stay in code rather than in a
prompt on purpose: a banking assistant's hard rules (refuse prompt-injection
attempts, never claim to have changed anything) should hold even if a prompt
is imperfectly worded or a model drifts, matching this project's existing
"business rules in code, not prompt" convention (see the account/product
specialist tools' own validation in ``src/utils/tools.py``).

``build_guardrail_middleware()`` is the single entry point: it returns a
fresh middleware stack to pass as ``create_agent(..., middleware=...)``.
"""

import re
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, AgentState, PIIMiddleware, hook_config
from langchain.agents.middleware.pii import apply_strategy, detect_credit_card, detect_email
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from utils import bank_data

# --- Before-model guardrail: prompt-injection / instruction-override -------

_INJECTION_PATTERNS = [
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

_INJECTION_REFUSAL = (
    "I can't follow instructions embedded in a message like that. Please ask "
    "a normal question about the selected customer's accounts, transactions, "
    "products, or offers."
)


def is_prompt_injection(text: str) -> bool:
    """Deterministic instruction-override / prompt-extraction check, shared by
    the middleware below and the non-LLM endpoint router."""
    return any(pattern.search(text) for pattern in _INJECTION_PATTERNS)


def redact_pii(text: str) -> str:
    """Redact emails and mask credit card numbers, the same strategies
    ``PIIMiddleware`` applies around every LLM call, for code paths that call
    a model without LangChain middleware (the Jev decisions router)."""
    text = apply_strategy(text, detect_email(text), "redact")
    return apply_strategy(text, detect_credit_card(text), "mask")


class PromptInjectionGuardMiddleware(AgentMiddleware):
    """Block messages that try to override instructions or extract the prompt."""

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
        )
        if last_human is None:
            return None
        if is_prompt_injection(str(last_human.content)):
            return {
                "messages": [AIMessage(content=_INJECTION_REFUSAL)],
                "jump_to": "end",
            }
        return None


# --- After-model guardrail: enforce query-only behaviour -------------------

_MUTATION_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi('| )?ve (approved|applied|opened|updated|processed|transferred)",
        r"\bi have (approved|applied|opened|updated|processed|transferred)",
        r"\bjóváírtam\b",
        r"\bjóváhagytam\b",
        r"\bmódosítottam\b",
        r"\bmegnyitottam\b",
        r"\belindítottam az igénylést\b",
    )
]

_QUERY_ONLY_NOTICE = (
    "I can only look up information - I have not changed, approved, or opened "
    "anything. Please action any changes through the usual banking systems."
)


class QueryOnlyEnforcementMiddleware(AgentMiddleware):
    """Rewrite any reply that claims to have performed a mutating action."""

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        if not messages:
            return None
        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return None
        text = str(last_message.content)
        if any(pattern.search(text) for pattern in _MUTATION_CLAIM_PATTERNS):
            return {
                "messages": [AIMessage(content=_QUERY_ONLY_NOTICE)],
                "jump_to": "end",
            }
        return None


# --- After-model guardrail: endpoint-entitlement access control ------------

_TIER_RANK = {"retail": 0, "premium": 1, "business": 2}


def check_endpoint_access(
    customer_id: str | None, matched: dict[str, Any] | None
) -> bool | None:
    """Return whether ``customer_id`` is denied the ``matched`` endpoint.

    ``True`` = denied, ``False`` = allowed, ``None`` = undecidable yet (no
    endpoint matched, or no customer selected, so the tier is unknown). This
    is the single, deterministic source of truth for the entitlement rule;
    the endpoint router, the officer chat loop's short-circuit, and the
    specialist tools all call it, so the refusal never depends on a prompt.
    """
    if not matched:
        return None
    customer = bank_data.find_customer(customer_id or "") if customer_id else None
    if customer is None:
        return None
    return _TIER_RANK[customer.entitlement_tier] < _TIER_RANK[matched["required_entitlement"]]


def access_denied_reply(matched: dict[str, Any]) -> str:
    """Fixed, code-written refusal for an endpoint the customer isn't entitled to."""
    return (
        "A kiválasztott ügyfél csomagja nem tartalmazza ezt a funkciót "
        f"({matched['menu_path']}); ehhez legalább "
        f"'{matched['required_entitlement']}' jogosultsági szint szükséges."
    )


# --- Coordinator-only: surface the router's result to the model ------------


class MatchedEndpointContextMiddleware(AgentMiddleware):
    """Make ``state["matched_endpoint"]`` visible to the coordinator's model.

    ``create_agent``'s ``system_prompt`` is a fixed string - the model only
    ever reads ``state["messages"]`` plus that string, so a plain state field
    like ``matched_endpoint`` (set from outside, by the endpoint-router agent
    run before this one) is otherwise invisible to it. This appends a short
    factual note about it to the system message on every model call, via
    ``wrap_model_call``, so the branch_coordinator prompt's instructions
    about ``matched_endpoint`` have something real to read.
    """

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> Any:
        matched = request.state.get("matched_endpoint")
        if matched is None:
            note = "\n\nEndpoint-router result for this turn: no endpoint matched."
        else:
            note = (
                "\n\nEndpoint-router result for this turn: "
                f"category={matched['category']}, menu_path={matched['menu_path']}, "
                f"required_entitlement={matched['required_entitlement']}, "
                f"access_denied={matched.get('access_denied')}."
            )
        base = request.system_message.content if request.system_message else ""
        request.system_message = SystemMessage(content=f"{base}{note}")
        return handler(request)


def build_coordinator_middleware() -> list[Any]:
    """Build the middleware stack for the branch coordinator.

    Extends ``build_guardrail_middleware()`` with
    ``MatchedEndpointContextMiddleware`` so the coordinator's model actually
    sees the endpoint-router's result, not just its prompt's instructions
    about it.
    """
    return build_guardrail_middleware() + [MatchedEndpointContextMiddleware()]


def build_guardrail_middleware() -> list[Any]:
    """Build a fresh before/after guardrail stack for one agent.

    Pass the result as ``create_agent(..., middleware=build_guardrail_middleware())``
    for every agent in the example (the coordinator and both specialists) so
    the same checks run around every LLM call, regardless of which agent
    makes it:

    - Before the model: block prompt-injection/instruction-override attempts
      (``PromptInjectionGuardMiddleware``).
    - Before AND after the model: redact emails and mask credit card numbers
      with LangChain's built-in ``PIIMiddleware``.
    - After the model: rewrite any reply that claims to have performed a
      mutating action, since this assistant is query-only
      (``QueryOnlyEnforcementMiddleware``).

    A fresh list is built on every call (rather than sharing one module-level
    list) because the account/product specialists are themselves rebuilt per
    officer question in ``create_branch_tools()``.
    """
    return [
        PromptInjectionGuardMiddleware(),
        PIIMiddleware(
            "email", strategy="redact", apply_to_input=True, apply_to_output=True
        ),
        PIIMiddleware(
            "credit_card", strategy="mask", apply_to_input=True, apply_to_output=True
        ),
        QueryOnlyEnforcementMiddleware(),
    ]
