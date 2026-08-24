"""Corporate offsite planner - a multi-agent, business-oriented example.

A coordinator (planner) delegates to three specialists, mirroring the models
used in ``simple_agent.py`` and ``advanced_agent.py``:

- Planner (``openai/gpt-oss-120b``): orchestrates the specialists and writes the
  final proposal.
- Venue & catering scout (``google/gemma-4-26b-a4b-it``): a vision model that
  compares candidate photos and recommends the best-looking option plus an
  alternative, rejecting the poor ones.
- Agenda writer (``poolside/laguna-s-2.1``): a text model that drafts the
  offsite agenda.

The example venue and meal images (good and bad looking) are real photos
downloaded from Wikimedia Commons and cached locally by
``utils.offsite_images``.
"""

from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from utils.config import load_config
from utils.file_util import encode_file_to_base64
from utils.offsite_images import generate_images

SEPARATOR = "-" * 80

openrouter_api_key = load_config()

# Model ids reused from simple_agent.py and advanced_agent.py.
PLANNER_MODEL = "openai/gpt-oss-120b"  # coordinator / planner
VISION_MODEL = "google/gemma-4-26b-a4b-it"  # gemma - venue & catering (images)
TEXT_MODEL = "poolside/laguna-s-2.1"  # laguna - agenda (text)

# Example images the vision model chooses from (good- and bad-looking options).
IMAGE_PATHS = generate_images()


def get_model(name: str, **kwargs: Any) -> BaseChatModel:
    """Create an OpenRouter chat model with the shared configuration."""
    return init_chat_model(
        model=name,
        model_provider="openrouter",
        api_key=openrouter_api_key,
        **kwargs,
    )


def _image_block(name: str) -> dict[str, str]:
    """Build an image content block for the given generated example image."""
    return {
        "type": "image",
        "base64": encode_file_to_base64(str(IMAGE_PATHS[name])),
        "mime_type": "image/jpeg",
    }


def _image_legend(options: dict[str, str]) -> str:
    """Render an 'Option -> file:// link' legend so the planner can cite images."""
    lines = [
        f"{label}: {IMAGE_PATHS[name].as_uri()}" for label, name in options.items()
    ]
    return "Image links:\n" + "\n".join(lines)


class OffsiteState(AgentState):
    destination: str
    attendee_count: str
    objective: str


# --- Specialist subagents ---------------------------------------------------

vision_model = get_model(VISION_MODEL, temperature=0.3, max_tokens=500)
text_model = get_model(TEXT_MODEL, temperature=0.7, max_tokens=500)

venue_agent = create_agent(
    model=vision_model,
    system_prompt=(
        "You are a venue scout. You are shown several candidate offsite venue "
        "photos labelled Option A, B, C and D. Compare their look and feel: "
        "lighting, tidiness, seating and overall atmosphere. Recommend the "
        "single best-looking venue as your top pick and one runner-up as an "
        "alternative. Explicitly reject any venue that looks dim, cramped or "
        "run down. Reply as: 'Best: <option> - <reason>. Alternative: "
        "<option> - <reason>. Rejected: <options> - <reason>.'"
    ),
)

catering_agent = create_agent(
    model=vision_model,
    system_prompt=(
        "You are a catering scout. You are shown several plated meal photos "
        "labelled Option A, B, C and D. Compare their presentation: colour, "
        "freshness and plating. Recommend the single best-looking meal as your "
        "top pick and one runner-up as an alternative. Explicitly reject any "
        "meal that looks greasy, dull or messy. Reply as: 'Best: <option> - "
        "<reason>. Alternative: <option> - <reason>. Rejected: <options> - "
        "<reason>.'"
    ),
)

agenda_agent = create_agent(
    model=text_model,
    system_prompt=(
        "You are an agenda writer for corporate offsites. Given the objective "
        "and attendee count, draft a concise one-day agenda with time blocks "
        "covering a kickoff, focused working sessions aligned to the "
        "objective, a team-building activity, meals and a wrap-up. Keep it to "
        "a tidy bulleted timeline."
    ),
)


# --- Coordinator tools ------------------------------------------------------


@tool
def choose_venue(runtime: ToolRuntime) -> str:
    """Vision scout reviews candidate venue photos and recommends the best plus an alternative."""
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
        _image_block("venue_good_1.jpg"),
        {"type": "text", "text": "Option B:"},
        _image_block("venue_good_2.jpg"),
        {"type": "text", "text": "Option C:"},
        _image_block("venue_bad_1.jpg"),
        {"type": "text", "text": "Option D:"},
        _image_block("venue_bad_2.jpg"),
    ]
    response = venue_agent.invoke({"messages": [HumanMessage(content=content)]})
    legend = _image_legend(
        {
            "Option A": "venue_good_1.jpg",
            "Option B": "venue_good_2.jpg",
            "Option C": "venue_bad_1.jpg",
            "Option D": "venue_bad_2.jpg",
        }
    )
    return f"{response['messages'][-1].content}\n\n{legend}"


@tool
def choose_catering(runtime: ToolRuntime) -> str:
    """Vision scout reviews candidate meal photos and recommends the best plus an alternative."""
    content: list[Any] = [
        {
            "type": "text",
            "text": (
                "Review these candidate catering meals and recommend the "
                "best-looking one and an alternative."
            ),
        },
        {"type": "text", "text": "Option A:"},
        _image_block("meal_good_1.jpg"),
        {"type": "text", "text": "Option B:"},
        _image_block("meal_good_2.jpg"),
        {"type": "text", "text": "Option C:"},
        _image_block("meal_bad_1.jpg"),
        {"type": "text", "text": "Option D:"},
        _image_block("meal_bad_2.jpg"),
    ]
    response = catering_agent.invoke({"messages": [HumanMessage(content=content)]})
    legend = _image_legend(
        {
            "Option A": "meal_good_1.jpg",
            "Option B": "meal_good_2.jpg",
            "Option C": "meal_bad_1.jpg",
            "Option D": "meal_bad_2.jpg",
        }
    )
    return f"{response['messages'][-1].content}\n\n{legend}"


@tool
def plan_agenda(runtime: ToolRuntime) -> str:
    """Agenda writer drafts the offsite agenda for the objective and attendee count."""
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
    """Record the offsite details once destination, attendee_count and objective are known.

    Call this alone, before delegating to the specialists, so the details are
    available to the other tools.
    """
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


coordinator = create_agent(
    model=get_model(PLANNER_MODEL, temperature=0.7, max_tokens=900),
    tools=[update_state, choose_venue, choose_catering, plan_agenda],
    state_schema=OffsiteState,
    system_prompt=(
        "You are a corporate offsite planner. First call update_state with the "
        "destination, attendee_count and objective from the request. Once that "
        "returns, delegate to your specialists: choose_venue and "
        "choose_catering (vision scouts) and plan_agenda (agenda writer). "
        "The scouts return an 'Image links:' legend mapping each option to a "
        "file:// URL. After collecting their answers, present a final proposal "
        "that clearly states the recommended venue, meal and agenda as the best "
        "choice, and lists the runner-up venue and meal as alternatives. For "
        "every venue and meal you mention, include its file:// image link taken "
        "from the matching legend so the reader can view the photo."
    ),
)


def run_offsite_demo() -> None:
    response = coordinator.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Plan a corporate offsite in Lisbon for 40 people. The "
                        "objective is to align the product team on next year's "
                        "roadmap."
                    )
                )
            ]
        },
        config={"tags": ["OFFSITE"], "recursion_limit": 40},
    )
    print(SEPARATOR)
    print("\nConversation:\n")
    for message in response["messages"]:
        role = getattr(message, "type", message.__class__.__name__)
        content = message.content
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        if str(content).strip():
            print(f"[{role}] {content}\n")

    print(SEPARATOR)
    print("\nFinal proposal:\n")
    print(response["messages"][-1].content)
    print(SEPARATOR)


if __name__ == "__main__":
    print("Corporate Offsite Planner is running...")
    run_offsite_demo()
