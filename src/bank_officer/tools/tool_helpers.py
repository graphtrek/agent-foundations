"""Small helpers shared by the data tools."""

from dataclasses import asdict

from data.endpoint_catalog import get_endpoint
from guardrails.endpoint_access import access_denied_reply, check_endpoint_access


def format_huf(amount: float | None) -> str:
    return "variable amount" if amount is None else f"{amount:,.0f} HUF"


def tier_denied(customer_id: str, endpoint_id: str) -> str | None:
    """In-tool entitlement re-check for tier-restricted GET endpoints, so the
    rule holds even if the router matched a different endpoint."""
    endpoint = get_endpoint(endpoint_id)
    if endpoint is not None and check_endpoint_access(customer_id, asdict(endpoint)):
        return f"ACCESS DENIED - relay this verbatim and stop: {access_denied_reply(asdict(endpoint))}"
    return None
