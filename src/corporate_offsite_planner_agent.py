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

from dataclasses import replace
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from utils.config import ModelConfig, load_config
from utils.file_util import encode_file_to_base64, load_prompt_template
from utils.offsite_images import generate_images

SEPARATOR = "-" * 80

config = load_config()
openrouter_api_key = config.openrouter_api_key

# Model configs loaded from the environment (see .env.example).
PLANNER_CONFIG = config.planner
VISION_CONFIG = config.vision
TEXT_CONFIG = config.text

# Example images the vision model chooses from (good- and bad-looking options).
IMAGE_PATHS = generate_images()


def get_model(config: ModelConfig) -> BaseChatModel:
    """Create an OpenRouter chat model from a ModelConfig."""
    params: dict[str, Any] = {
        "model": config.name,
        "model_provider": "openrouter",
        "api_key": openrouter_api_key,
        # Sampling temperature: higher = more creative, lower = more deterministic.
        "temperature": config.temperature,
        # Upper bound on generated tokens for the reply.
        "max_tokens": config.max_tokens,
    }
    # Only send tuning params that are set so provider defaults apply otherwise.
    if config.top_p is not None:
        # Nucleus sampling: sample from the top tokens summing to this probability.
        params["top_p"] = config.top_p
    if config.frequency_penalty is not None:
        # Discourage repeating tokens in proportion to how often they appeared.
        params["frequency_penalty"] = config.frequency_penalty
    if config.presence_penalty is not None:
        # Discourage reusing any already-seen token, nudging toward new topics.
        params["presence_penalty"] = config.presence_penalty
    if config.seed is not None:
        # Fix the RNG seed for reproducible outputs on identical inputs.
        params["seed"] = config.seed
    return init_chat_model(**params)


def load_agent(name: str, base_config: ModelConfig) -> tuple[str, BaseChatModel]:
    """Load a prompt template and build its model, applying any frontmatter overrides."""
    system_prompt, overrides = load_prompt_template(name)
    return system_prompt, get_model(replace(base_config, **overrides))


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

venue_prompt, venue_model = load_agent("venue_agent", VISION_CONFIG)
venue_agent = create_agent(model=venue_model, system_prompt=venue_prompt)

catering_prompt, catering_model = load_agent("catering_agent", VISION_CONFIG)
catering_agent = create_agent(model=catering_model, system_prompt=catering_prompt)

agenda_prompt, agenda_model = load_agent("agenda_agent", TEXT_CONFIG)
agenda_agent = create_agent(model=agenda_model, system_prompt=agenda_prompt)


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


coordinator_prompt, coordinator_model = load_agent("coordinator", PLANNER_CONFIG)
coordinator = create_agent(
    model=coordinator_model,
    tools=[update_state, choose_venue, choose_catering, plan_agenda],
    state_schema=OffsiteState,
    system_prompt=coordinator_prompt,
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
