"""Bank branch officer chat assistant - a multi-agent, query-only example.

An officer serving a walk-in customer chats with an assistant backed by a
coordinator agent (``create_agent()``) that delegates to three specialists,
mirroring the pattern in ``corporate_offsite_planner_agent.py``:

- Account/transactions specialist: balances and transaction history.
- Product/offers specialist: product catalog, personalized discounts, existing loans.
- Service specialist: cards and limits, loan-application status, profile, support tickets.

Before the coordinator sees each message, an endpoint router runs first:
not a chat agent but a TypeSafe Jev decision model on OpenRouter's Decisions
API (``utils.decision_router.EndpointRouter``), which picks the best REST
endpoint in a mock web banking app catalog; code then flags whether the
selected customer's entitlement tier covers it. The access rule
is enforced in code, never by a prompt: when the verdict is "denied", the
chat loop answers with a fixed refusal and the coordinator is not called at
all; the specialist tools re-check it as well, for a customer selected
mid-turn. Otherwise the coordinator reads the router's result
(``matched_endpoint`` in ``BranchState``) to help choose a specialist.

Every reply reaches the officer through ``BranchSession._deliver()``
(``utils.branch_session``, shared with the web chat in
``bank_officer_web.py``), a deterministic response gateway (no LLM), and
the coordinator's conversation thread is reset whenever the officer switches to a different customer, so one
customer's data never stays in context while serving the next one.

The coordinator also owns direct tools for customer lookup/selection
(``list_customers``, ``select_customer``) so the officer can serve several
mock customers in one session. This example is query-only: no tool mutates
account or product data, and no human-approval gate is needed since the
officer is already the human in the loop.

Run with: uv run python src/bank_officer_agent.py
"""

import logging
import os
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from utils.config import load_config
from utils.agent_spec import load_agent_factories, load_agent_specs
from utils.branch_session import BranchSession
from utils.decision_router import EndpointRouter
from utils.tools import (
    BranchContext,
    BranchState,
    create_branch_tools,
)

SEPARATOR = "-" * 80
CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "bank_officer_agent.log"
EXIT_WORDS = {"exit", "quit", "kilépés"}
logger = logging.getLogger(__name__)

config = load_config()
openrouter_api_key = config.openrouter_api_key

# Every agent of this example is defined by its own Markdown file in
# src/resources/agents/bank_officer/ (model settings, tool list, guardrail
# stack and system prompt). None need vision, so the TEXT_* config is the
# shared base that each file's model directives override.
BASE_CONFIG = config.text
AGENTS_EXAMPLE = "bank_officer"


def build_agents() -> tuple[EndpointRouter, Any]:
    """Build the endpoint router and the coordinator (with its three specialist
    tools) from their agent definition files. The coordinator's in-memory
    checkpointer keys threads by id, so one coordinator can serve several
    sessions as long as each uses its own thread id prefix."""
    factories = load_agent_factories(AGENTS_EXAMPLE, BASE_CONFIG, openrouter_api_key)
    branch_tools = create_branch_tools(
        factories["account_specialist"],
        factories["product_specialist"],
        factories["service_specialist"],
    )
    coordinator = factories["branch_coordinator"].build(
        branch_tools,
        state_schema=BranchState,
        context_schema=BranchContext,
        checkpointer=InMemorySaver(),
    )
    # The router is a decision model (kind: decision), not a chat agent, and
    # is stateless across turns: it sees only the current question.
    endpoint_router = EndpointRouter(
        load_agent_specs(AGENTS_EXAMPLE)["endpoint_router"], openrouter_api_key
    )
    return endpoint_router, coordinator


def run_officer_chat() -> None:
    """Run the interactive officer chat loop until an exit word is typed."""
    endpoint_router, coordinator = build_agents()
    session = BranchSession(
        endpoint_router,
        coordinator,
        BranchContext(officer_id="officer-demo", branch_id="branch-buda"),
    )

    print(SEPARATOR)
    print("Bank Branch Officer Assistant - type 'exit', 'quit', or 'kilépés' to quit.")
    print(SEPARATOR)

    while True:
        try:
            user_input = input("Tisztviselő: ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input.lower() in EXIT_WORDS:
            break
        for event, data in session.stream_turn(user_input):
            if event == "tool_call":
                print(f"  … {data['name']}")
            elif event == "reply":
                print(f"Asszisztens: {data['text']}\n")

    conversation_path = session.save(CONVERSATIONS_DIR)
    if conversation_path is not None:
        logger.info("Conversation saved to %s", conversation_path)
        print(SEPARATOR)
        print(f"Conversation saved to: {conversation_path}")
    else:
        print("No conversation to save.")


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
    print("Bank Branch Officer Assistant is running...")
    run_officer_chat()
