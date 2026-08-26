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

import logging
import os
from pathlib import Path
from typing import Any, cast

from langchain.agents import AgentState, create_agent
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from utils.config import load_config
from utils.conversation_util import (
    message_text,
    message_was_truncated,
    save_conversation,
)
from utils.model_util import load_configured_model
from utils.offsite_images import generate_images
from utils.tools import create_offsite_tools

SEPARATOR = "-" * 80
CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "corporate_offsite_planner.log"
REQUIRED_TOOL_NAMES = {"update_state", "choose_venue", "choose_catering", "plan_agenda"}
MAX_COORDINATOR_ATTEMPTS = 3
logger = logging.getLogger(__name__)

config = load_config()
openrouter_api_key = config.openrouter_api_key

# Model configs loaded from the environment (see .env.example).
PLANNER_CONFIG = config.planner
VISION_CONFIG = config.vision
TEXT_CONFIG = config.text

# Example images the vision model chooses from (good- and bad-looking options).
IMAGE_PATHS = generate_images()


class OffsiteState(AgentState):
    destination: str
    attendee_count: str
    objective: str


# --- Specialist subagents ---------------------------------------------------

venue_prompt, venue_model = load_configured_model(
    "venue_agent", VISION_CONFIG, openrouter_api_key
)
venue_agent = create_agent(model=venue_model, system_prompt=venue_prompt)

catering_prompt, catering_model = load_configured_model(
    "catering_agent", VISION_CONFIG, openrouter_api_key
)
catering_agent = create_agent(model=catering_model, system_prompt=catering_prompt)

agenda_prompt, agenda_model = load_configured_model(
    "agenda_agent", TEXT_CONFIG, openrouter_api_key
)
agenda_agent = create_agent(model=agenda_model, system_prompt=agenda_prompt)


coordinator_prompt, coordinator_model = load_configured_model(
    "coordinator", PLANNER_CONFIG, openrouter_api_key
)
offsite_tools = create_offsite_tools(
    venue_agent, catering_agent, agenda_agent, IMAGE_PATHS
)
coordinator = create_agent(
    model=coordinator_model,
    tools=offsite_tools,
    state_schema=OffsiteState,
    system_prompt=coordinator_prompt,
)


def _conversation_status(messages: list[Any]) -> tuple[set[str], bool]:
    """Return missing required tools and whether a final answer follows them."""
    completed_tools = {
        message.name
        for message in messages
        if getattr(message, "type", None) == "tool" and message.name
    }
    missing_tools = REQUIRED_TOOL_NAMES - completed_tools
    if missing_tools:
        logger.debug(
            "Conversation is missing required tools: %s", sorted(missing_tools)
        )
        return missing_tools, False

    last_tool_index = max(
        index
        for index, message in enumerate(messages)
        if getattr(message, "type", None) == "tool"
        and message.name in REQUIRED_TOOL_NAMES
    )
    has_final_answer = any(
        getattr(message, "type", None) == "ai"
        and message_text(message.content)
        and not message_was_truncated(message)
        for message in messages[last_tool_index + 1 :]
    )
    logger.debug("Conversation status: final_answer=%s", has_final_answer)
    return set(), has_final_answer


def _run_coordinator_to_completion(user_prompt: str) -> dict[str, Any]:
    """Run the coordinator, resuming boundedly if it ends before completion."""
    state: dict[str, Any] = {"messages": [HumanMessage(content=user_prompt)]}
    config: RunnableConfig = {"tags": ["OFFSITE"], "recursion_limit": 40}
    logger.info("Starting coordinator run")

    for attempt in range(1, MAX_COORDINATOR_ATTEMPTS + 1):
        logger.info("Coordinator attempt %d/%d", attempt, MAX_COORDINATOR_ATTEMPTS)
        response = cast(
            dict[str, Any], coordinator.invoke(cast(Any, state), config=config)
        )
        logger.debug("Coordinator returned %d messages", len(response["messages"]))
        missing_tools, has_final_answer = _conversation_status(response["messages"])
        if not missing_tools and has_final_answer:
            logger.info("Coordinator completed successfully on attempt %d", attempt)
            return response
        if attempt == MAX_COORDINATOR_ATTEMPTS:
            missing = ", ".join(sorted(missing_tools)) or "final proposal"
            logger.error("Coordinator failed to complete; missing: %s", missing)
            raise RuntimeError(
                f"Coordinator did not complete after {attempt} attempts; missing: {missing}."
            )

        remaining_work = (
            f"Call these missing tools: {', '.join(sorted(missing_tools))}. "
            if missing_tools
            else (
                "All specialist results are available. The previous answer was "
                "missing or truncated, so write a concise, complete replacement. "
            )
        )
        logger.warning(
            "Coordinator incomplete; requesting recovery: %s", remaining_work
        )
        recovery_message = HumanMessage(
            content=(
                "Continue and complete the offsite plan. "
                f"{remaining_work}Then provide the final proposal."
            ),
            additional_kwargs={"internal_recovery": True},
        )
        state = {**response, "messages": [*response["messages"], recovery_message]}

    raise RuntimeError("Coordinator completion loop exited unexpectedly.")


def run_offsite_demo() -> None:
    user_prompt = (
        "Plan a corporate offsite in Lisbon for 40 people. The objective is "
        "to align the product team on next year's roadmap."
    )
    logger.info("Running corporate offsite demo")
    response = _run_coordinator_to_completion(user_prompt)
    conversation_path = save_conversation(
        user_prompt, response["messages"], CONVERSATIONS_DIR, IMAGE_PATHS
    )
    logger.info("Conversation saved to %s", conversation_path)
    print(SEPARATOR)
    print("\nConversation:\n")
    for message in response["messages"]:
        role = getattr(message, "type", message.__class__.__name__)
        content = message_text(message.content)
        if content:
            print(f"[{role}] {content}\n")

    print(SEPARATOR)
    print("\nFinal proposal:\n")
    print(response["messages"][-1].content)
    print(SEPARATOR)
    print(f"Conversation saved to: {conversation_path}")


if __name__ == "__main__":
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    print("Corporate Offsite Planner is running...")
    run_offsite_demo()
