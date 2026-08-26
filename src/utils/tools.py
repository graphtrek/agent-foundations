from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain.agents import AgentState
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.types import Command

from utils.offsite_images import image_content_block, image_legend

duckduckgo_client = DuckDuckGoSearchResults(output_format="string")


def search_web(query: str) -> str:
    """Search the web for information."""
    return duckduckgo_client.invoke(query)


web_search = tool("web_search")(search_web)


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


def create_offsite_tools(
    venue_agent: Any,
    catering_agent: Any,
    agenda_agent: Any,
    image_paths: dict[str, Path],
) -> list[Any]:
    """Create coordinator tools bound to specialist agents and local images."""

    @tool
    def choose_venue(runtime: ToolRuntime) -> str:
        """Review venue photos and recommend the best plus an alternative."""
        destination = runtime.state.get("destination", "the destination")
        content: list[Any] = [
            {
                "type": "text",
                "text": (
                    f"Review these candidate offsite venues in {destination} and "
                    "recommend the best-looking one and an alternative."
                ),
            },
            {"type": "text", "text": "Option A:"},
            image_content_block(image_paths["venue_good_1.jpg"]),
            {"type": "text", "text": "Option B:"},
            image_content_block(image_paths["venue_good_2.jpg"]),
            {"type": "text", "text": "Option C:"},
            image_content_block(image_paths["venue_bad_1.jpg"]),
            {"type": "text", "text": "Option D:"},
            image_content_block(image_paths["venue_bad_2.jpg"]),
        ]
        response = venue_agent.invoke({"messages": [HumanMessage(content=content)]})
        legend = image_legend(
            {
                "Option A": "venue_good_1.jpg",
                "Option B": "venue_good_2.jpg",
                "Option C": "venue_bad_1.jpg",
                "Option D": "venue_bad_2.jpg",
            },
            image_paths,
        )
        return f"{response['messages'][-1].content}\n\n{legend}"

    @tool
    def choose_catering(runtime: ToolRuntime) -> str:
        """Review meal photos and recommend the best plus an alternative."""
        content: list[Any] = [
            {
                "type": "text",
                "text": (
                    "Review these candidate catering meals and recommend the "
                    "best-looking one and an alternative."
                ),
            },
            {"type": "text", "text": "Option A:"},
            image_content_block(image_paths["meal_good_1.jpg"]),
            {"type": "text", "text": "Option B:"},
            image_content_block(image_paths["meal_good_2.jpg"]),
            {"type": "text", "text": "Option C:"},
            image_content_block(image_paths["meal_bad_1.jpg"]),
            {"type": "text", "text": "Option D:"},
            image_content_block(image_paths["meal_bad_2.jpg"]),
        ]
        response = catering_agent.invoke({"messages": [HumanMessage(content=content)]})
        legend = image_legend(
            {
                "Option A": "meal_good_1.jpg",
                "Option B": "meal_good_2.jpg",
                "Option C": "meal_bad_1.jpg",
                "Option D": "meal_bad_2.jpg",
            },
            image_paths,
        )
        return f"{response['messages'][-1].content}\n\n{legend}"

    @tool
    def plan_agenda(runtime: ToolRuntime) -> str:
        """Draft the agenda for the objective and attendee count."""
        objective = runtime.state.get("objective", "team alignment")
        attendee_count = runtime.state.get("attendee_count", "the team")
        query = (
            f"Draft a one-day offsite agenda for {attendee_count} attendees with "
            f"the objective: {objective}."
        )
        response = agenda_agent.invoke({"messages": [HumanMessage(content=query)]})
        return response["messages"][-1].content

    @tool
    def update_state(
        destination: str,
        attendee_count: str,
        objective: str,
        runtime: ToolRuntime,
    ) -> Command:
        """Record the destination, attendee count, and objective in agent state."""
        return Command(
            update={
                "destination": destination,
                "attendee_count": attendee_count,
                "objective": objective,
                "messages": [
                    ToolMessage(
                        content="Successfully recorded offsite details.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return [update_state, choose_venue, choose_catering, plan_agenda]
