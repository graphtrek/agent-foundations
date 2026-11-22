"""Bank branch officer chat assistant - a multi-agent, query-only example.

An officer serving a walk-in customer chats with an assistant backed by a
coordinator agent (``create_agent()``) that - in the default ``router``
architecture profile - delegates to three specialists (other profiles in
``architectures/`` rearrange or drop the router, coordinator and specialists):

- Account/transactions specialist: balances and transaction history.
- Product/offers specialist: product catalog, personalized discounts, existing loans.
- Service specialist: cards and limits, loan-application status, profile, support tickets.

Before the coordinator sees each message, an endpoint router runs first:
not a chat agent but a TypeSafe Jev decision model on OpenRouter's Decisions
API (``decision_router.EndpointRouter``), which picks the best REST
endpoint in a mock web banking app catalog; code then flags whether the
selected customer's entitlement tier covers it. The access rule
is enforced in code, never by a prompt: when the verdict is "denied", the
chat loop answers with a fixed refusal and the coordinator is not called at
all; the specialist tools re-check it as well, for a customer selected
mid-turn. Otherwise the coordinator reads the router's result
(``matched_endpoint`` in ``BranchState``) to help choose a specialist.

Every reply reaches the officer through ``BranchSession._deliver()``
(``branch_session``, shared with the web chat in
``main.py``), a deterministic response gateway (no LLM), and
the coordinator's conversation thread is reset whenever the officer switches to a different customer, so one
customer's data never stays in context while serving the next one.

The coordinator also owns direct tools for customer lookup/selection
(``list_customers``, ``select_customer``) so the officer can serve several
mock customers in one session. This example is query-only: no tool mutates
account or product data, and no human-approval gate is needed since the
officer is already the human in the loop.

Run with: uv run python src/bank_officer/terminal.py [--arch <profile id>]
"""

import argparse
import logging
import os
from pathlib import Path

from architecture import PipelineRegistry
from branch_session import BranchSession
from config import load_config
from tools import BranchContext

SEPARATOR = "-" * 80
CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "conversations"
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOGS_DIR / "bank_officer_agent.log"
EXIT_WORDS = {"exit", "quit", "kilépés"}
logger = logging.getLogger(__name__)

config = load_config()
openrouter_api_key = config.openrouter_api_key

# Every agent is defined by its own Markdown file in its architecture's folder,
# src/bank_officer/architectures/<id>/ (model settings, tool list, guardrail
# stack and system prompt). None need vision, so the TEXT_* config is the
# shared base that each file's model directives override.
BASE_CONFIG = config.text
DEFAULT_ARCHITECTURE = os.environ.get("BANK_ARCH", "router")

# Every architecture (router or not, coordinator, specialists) is a folder in
# src/bank_officer/architectures/ with architecture.yaml and its agent files; the registry
# builds a profile's agents on first use and caches them. One coordinator can
# serve several sessions as long as each uses its own thread id prefix.
REGISTRY = PipelineRegistry(BASE_CONFIG, openrouter_api_key)


def run_officer_chat(architecture: str = DEFAULT_ARCHITECTURE) -> None:
    """Run the interactive officer chat loop until an exit word is typed."""
    pipeline = REGISTRY.get(architecture)
    session = BranchSession(
        pipeline.router,
        pipeline.coordinator,
        BranchContext(officer_id="officer-demo", branch_id="branch-buda"),
        architecture=architecture,
    )

    print(SEPARATOR)
    print(f"Architecture: {architecture} - {pipeline.profile.label}")
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
    parser = argparse.ArgumentParser(description="Bank branch officer terminal chat")
    parser.add_argument(
        "--arch",
        default=DEFAULT_ARCHITECTURE,
        help="architecture profile id (src/bank_officer/architectures/<id>.yaml)",
    )
    args = parser.parse_args()
    print("Bank Branch Officer Assistant is running...")
    run_officer_chat(args.arch)
