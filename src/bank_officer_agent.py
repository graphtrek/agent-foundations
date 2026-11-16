"""Bank branch officer chat assistant - a multi-agent, query-only example.

An officer serving a walk-in customer chats with an assistant backed by a
coordinator agent (``create_agent()``) that delegates to two specialists,
mirroring the pattern in ``corporate_offsite_planner_agent.py``:

- Account/transactions specialist: balances and transaction history.
- Product/offers specialist: product catalog and personalized discounts.

Before the coordinator sees each message, a separate endpoint-router agent
(``build_endpoint_router()``) runs first, matching the officer's question to
the best REST endpoint in a mock web banking app catalog and flagging
whether the selected customer's entitlement tier covers it; the coordinator
reads that result (``matched_endpoint`` in ``BranchState``) to help choose a
specialist or to refuse outright.

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
from typing import Any, cast

from langchain.agents import create_agent
from langchain.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from utils.config import load_config
from utils.conversation_util import message_text, save_conversation
from utils.guardrails import build_coordinator_middleware, build_endpoint_router_middleware
from utils.model_util import load_configured_model
from utils.tools import (
    BranchContext,
    BranchState,
    create_branch_tools,
    create_endpoint_router_tools,
)

SEPARATOR = "-" * 80
CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOGS_DIR / "bank_officer_agent.log"
EXIT_WORDS = {"exit", "quit", "kilépés"}
THREAD_ID = "branch-visit-1"
logger = logging.getLogger(__name__)

config = load_config()
openrouter_api_key = config.openrouter_api_key

# None of the three roles (coordinator, account specialist, product
# specialist) need vision, so the TEXT_* config is the shared base; each
# prompt file's yaml block overrides whatever it needs per role.
BASE_CONFIG = config.text


def build_coordinator() -> Any:
    """Load prompts/models for all three roles and assemble the coordinator."""
    account_prompt, account_model = load_configured_model(
        "account_specialist", BASE_CONFIG, openrouter_api_key
    )
    product_prompt, product_model = load_configured_model(
        "product_specialist", BASE_CONFIG, openrouter_api_key
    )
    coordinator_prompt, coordinator_model = load_configured_model(
        "branch_coordinator", BASE_CONFIG, openrouter_api_key
    )

    branch_tools = create_branch_tools(
        account_model, account_prompt, product_model, product_prompt
    )
    return create_agent(
        model=coordinator_model,
        tools=branch_tools,
        state_schema=BranchState,
        context_schema=BranchContext,
        system_prompt=coordinator_prompt,
        checkpointer=InMemorySaver(),
        middleware=build_coordinator_middleware(),
    )


def build_endpoint_router() -> Any:
    """Assemble the endpoint-router agent that runs before the coordinator on
    every turn. It is stateless across turns (no checkpointer), the same way
    the on-the-fly account/product specialist agents are, since it needs no
    memory of its own between officer questions.
    """
    router_prompt, router_model = load_configured_model(
        "endpoint_specialist", BASE_CONFIG, openrouter_api_key
    )
    return create_agent(
        model=router_model,
        tools=create_endpoint_router_tools(),
        state_schema=BranchState,
        context_schema=BranchContext,
        system_prompt=router_prompt,
        middleware=build_endpoint_router_middleware(),
    )


def run_officer_chat() -> None:
    """Run the interactive officer chat loop until an exit word is typed."""
    coordinator = build_coordinator()
    endpoint_router = build_endpoint_router()
    thread_config: RunnableConfig = {
        "configurable": {"thread_id": THREAD_ID},
        "tags": ["BRANCH_OFFICER"],
        "recursion_limit": 40,
    }
    context = BranchContext(officer_id="officer-demo", branch_id="branch-buda")

    print(SEPARATOR)
    print("Bank Branch Officer Assistant - type 'exit', 'quit', or 'kilépés' to quit.")
    print(SEPARATOR)

    first_prompt: str | None = None
    final_messages: list[Any] = []
    current_customer_id: str | None = None

    while True:
        try:
            user_input = input("Tisztviselő: ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input.lower() in EXIT_WORDS:
            break
        if first_prompt is None:
            first_prompt = user_input

        logger.info("Officer turn: %s", user_input)
        router_response = cast(
            dict[str, Any],
            endpoint_router.invoke(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "current_customer_id": current_customer_id,
                },
                config={"tags": ["ENDPOINT_ROUTER"], "recursion_limit": 40},
                context=context,
            ),
        )
        matched_endpoint = router_response.get("matched_endpoint")
        logger.info("Matched endpoint: %s", matched_endpoint)

        response = cast(
            dict[str, Any],
            coordinator.invoke(
                {
                    "messages": [HumanMessage(content=user_input)],
                    "matched_endpoint": matched_endpoint,
                },
                config=thread_config,
                context=context,
            ),
        )
        final_messages = response["messages"]
        current_customer_id = response.get("current_customer_id", current_customer_id)
        reply = message_text(final_messages[-1].content)
        print(f"Asszisztens: {reply}\n")

    if final_messages and first_prompt:
        conversation_path = save_conversation(
            first_prompt,
            final_messages,
            CONVERSATIONS_DIR,
            title="Bank Branch Officer Chat Conversation",
            assistant_heading="Assistant",
        )
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
