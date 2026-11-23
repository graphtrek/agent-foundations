"""The coordinator's own tools: customer lookup, branch info and its specialists."""

from collections.abc import Sequence
from typing import Any

from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from agents.agent_spec import AgentFactory
from data import bank_data
from tools.branch_context import BranchContext, BranchState
from tools.public_info_tools import create_public_info_tools
from tools.specialist_tools import (
    SpecialistBinding,
    make_flat_tool,
    make_specialist_tool,
)
from tools.synthesizer_tool import make_synthesizer_tool
from tools.tool_groups import CUSTOMER_FREE_GROUPS, TOOL_GROUPS


def create_branch_tools(
    specialists: Sequence[SpecialistBinding] = (),
    flat: bool = False,
    synthesizer: AgentFactory | None = None,
) -> list[Any]:
    """Create the coordinator's own tools: customer lookup, branch info and -
    by the architecture profile - either one ``ask_<id>`` wrapper per
    specialist (``flat=False``) or every customer-scoped data tool directly
    (``flat=True``, the single-agent baseline).

    The customer-scoped tools can't be static (the customer is selected
    mid-session), so each wrapper builds a fresh specialist agent with
    customer-scoped tools on every call, from the agent's own Markdown
    definition (``AgentFactory``, model built once per pipeline).
    """

    @tool
    def list_customers() -> str:
        """List every customer available to select in this demo branch session."""
        return "\n".join(
            f"- {c.customer_id}: {c.full_name} (born {c.date_of_birth.isoformat()})"
            for c in bank_data.list_customers()
        )

    @tool
    def select_customer(
        name_or_id: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> Command:
        """Select the customer currently at the branch desk, by name or id."""
        customer = bank_data.find_customer(name_or_id)
        if customer is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"No customer matches '{name_or_id}'. "
                                "Use list_customers to see available customers."
                            ),
                            tool_call_id=runtime.tool_call_id,
                        )
                    ]
                }
            )
        return Command(
            update={
                "current_customer_id": customer.customer_id,
                "messages": [
                    ToolMessage(
                        content=(
                            f"Selected customer {customer.full_name} "
                            f"({customer.customer_id})."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    direct = [list_customers, select_customer, *create_public_info_tools()]
    if flat:
        scoped = [
            make_flat_tool(group, t)
            for group, builder in TOOL_GROUPS.items()
            if group not in CUSTOMER_FREE_GROUPS
            for t in builder("")
        ]
    else:
        scoped = [make_specialist_tool(b) for b in specialists]
        if synthesizer is not None:
            scoped.append(make_synthesizer_tool(synthesizer))
    return direct + scoped
