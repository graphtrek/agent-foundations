from pathlib import Path
from typing import Any

from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from offsite_images import image_content_block, image_legend


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
