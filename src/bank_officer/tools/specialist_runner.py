"""Shared code for the wrapper tools that run a specialist sub-agent."""

import logging
from typing import Any

from langchain.messages import HumanMessage

from guardrails.endpoint_access import access_denied_reply, check_endpoint_access
from tools.branch_context import BranchState

SPECIALIST_RECURSION_LIMIT = 60
SPECIALIST_FAILURE_REPLY = (
    "The specialist could not answer this question right now. Do not guess - "
    "tell the officer the information is temporarily unavailable."
)
logger = logging.getLogger(__name__)


def specialist_gate(state: BranchState) -> str | None:
    """Deterministic pre-checks shared by the specialist wrapper tools.

    Returns a fixed reply when the specialist must not run: no customer is
    selected, or the customer selected *now* (possibly earlier in this same
    turn) is not entitled to the endpoint the router matched. Re-checking
    here keeps the entitlement rule enforced in code even when the customer
    is selected mid-turn.
    """
    customer_id = state.get("current_customer_id")
    if not customer_id:
        return "No customer is currently selected. Call select_customer first."
    matched = state.get("matched_endpoint")
    if matched is not None and check_endpoint_access(customer_id, matched):
        return f"ACCESS DENIED - relay this verbatim and stop: {access_denied_reply(matched)}"
    return None


def run_specialist(agent: Any, question: str) -> str:
    """Invoke a specialist with a bounded loop; fall back to a fixed reply on
    any failure (recursion limit, provider error, timeout) instead of letting
    the coordinator improvise."""
    try:
        response = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"recursion_limit": SPECIALIST_RECURSION_LIMIT},
        )
    except Exception:
        logger.exception("Specialist call failed")
        return SPECIALIST_FAILURE_REPLY
    return response["messages"][-1].content
