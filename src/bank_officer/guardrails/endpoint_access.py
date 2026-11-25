"""Endpoint-entitlement access control: the single source of truth for the tier rule."""

from typing import Any

from data import bank_data
from localization.messages import text

TIER_RANK = {"retail": 0, "premium": 1, "business": 2}


def check_endpoint_access(
    customer_id: str | None, matched: dict[str, Any] | None
) -> bool | None:
    """Return whether ``customer_id`` is denied the ``matched`` endpoint.

    ``True`` = denied, ``False`` = allowed, ``None`` = undecidable yet (no
    endpoint matched, or no customer selected, so the tier is unknown). The
    endpoint router, the session's short-circuit and the specialist tools all
    call it, so the refusal never depends on a prompt.
    """
    if not matched:
        return None
    customer = bank_data.find_customer(customer_id or "") if customer_id else None
    if customer is None:
        return None
    return TIER_RANK[customer.entitlement_tier] < TIER_RANK[matched["required_entitlement"]]


def access_denied_reply(matched: dict[str, Any], language: str | None = None) -> str:
    """Fixed, code-written refusal for an endpoint the customer isn't entitled to,
    in the current turn's language unless ``language`` says otherwise."""
    return text(
        "access_denied",
        language,
        menu_path=matched["menu_path"],
        required_entitlement=matched["required_entitlement"],
    )
