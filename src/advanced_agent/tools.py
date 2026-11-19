from dataclasses import dataclass
from typing import Any

from langchain.agents import AgentState
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command


@dataclass
class SupportContext:
    user_id: str
    locale: str = "en"
    customer_tier: str = "standard"
    refund_limit: float = 50.0


class CustomerState(AgentState):
    ticket_id: str | None
    issue_category: str | None
    status: str | None


def create_customer_support_tools() -> list[Any]:
    """Create the tools used by the customer support agent."""

    @tool
    def get_support_policy(runtime: ToolRuntime[SupportContext]) -> str:
        """Return the support policy for the current user and runtime context."""
        return (
            f"User {runtime.context.user_id} is a "
            f"{runtime.context.customer_tier} customer. The maximum self-service "
            f"refund is {runtime.context.refund_limit:.2f}."
        )

    @tool
    def update_ticket(
        ticket_id: str,
        issue_category: str,
        status: str,
        runtime: ToolRuntime[SupportContext, CustomerState],
    ) -> Command:
        """Store ticket details in conversation state."""
        return Command(
            update={
                "ticket_id": ticket_id,
                "issue_category": issue_category,
                "status": status,
                "messages": [
                    ToolMessage(
                        content=f"Ticket {ticket_id} updated to {status}.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    @tool
    def read_ticket(runtime: ToolRuntime[SupportContext, CustomerState]) -> str:
        """Read the ticket details accumulated in conversation state."""
        ticket_id = runtime.state.get("ticket_id")
        if not ticket_id:
            return "No ticket has been created yet."
        return (
            f"Ticket {ticket_id}: "
            f"{runtime.state.get('issue_category', 'unknown issue')}, "
            f"status {runtime.state.get('status', 'unknown')}."
        )

    return [get_support_policy, update_ticket, read_ticket]
