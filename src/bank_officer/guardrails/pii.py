"""PII redaction for code paths that call a model without LangChain middleware."""

from langchain.agents.middleware.pii import (
    apply_strategy,
    detect_credit_card,
    detect_email,
)


def redact_pii(text: str) -> str:
    """Redact emails and mask credit card numbers, the same strategies
    ``PIIMiddleware`` applies around every LLM call (used by the Jev decisions
    router and for tool-result previews)."""
    text = apply_strategy(text, detect_email(text), "redact")
    return apply_strategy(text, detect_credit_card(text), "mask")
