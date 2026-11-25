"""The guardrail middleware stacks passed to ``create_agent(..., middleware=...)``.

The checks stay in code rather than in a prompt on purpose: a banking
assistant's hard rules (refuse prompt-injection attempts, never claim to have
changed anything) must hold even if a prompt is imperfectly worded or a model
drifts. The Jev router has no LangChain middleware; it runs the same checks
in code (``is_prompt_injection()`` and ``redact_pii()``).
"""

from typing import Any

from langchain.agents.middleware import PIIMiddleware

from guardrails.matched_endpoint_context import MatchedEndpointContextMiddleware
from guardrails.prompt_injection import PromptInjectionGuardMiddleware
from guardrails.query_only import QueryOnlyEnforcementMiddleware
from guardrails.reply_language import ReplyLanguageMiddleware


def build_guardrail_middleware() -> list[Any]:
    """Build a fresh before/after guardrail stack for one agent.

    - Before the model: block prompt-injection attempts.
    - Before AND after the model: redact emails and mask credit card numbers.
    - After the model: rewrite any reply that claims a mutating action.

    A fresh list is built on every call because the specialists are rebuilt
    per officer question.
    """
    return [
        PromptInjectionGuardMiddleware(),
        PIIMiddleware("email", strategy="redact", apply_to_input=True, apply_to_output=True),
        PIIMiddleware("credit_card", strategy="mask", apply_to_input=True, apply_to_output=True),
        QueryOnlyEnforcementMiddleware(),
    ]


def build_coordinator_middleware() -> list[Any]:
    """The guardrail stack plus the router-result context for the coordinator."""
    return build_guardrail_middleware() + [MatchedEndpointContextMiddleware()]


def build_research_middleware() -> list[Any]:
    """The guardrail stack plus the reply language, for the web-search coordinator."""
    return build_guardrail_middleware() + [ReplyLanguageMiddleware()]
