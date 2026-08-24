from dataclasses import dataclass
from pprint import pprint

from langchain.agents import AgentState, create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from utils.config import load_config

openrouter_api_key = load_config()


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


@tool
def get_support_policy(runtime: ToolRuntime[SupportContext]) -> str:
    """Return the support policy for the current user and runtime context."""
    return (
        f"User {runtime.context.user_id} is a {runtime.context.customer_tier} customer. "
        f"The maximum self-service refund is {runtime.context.refund_limit:.2f}."
    )


@tool
def update_ticket(
    ticket_id: str,
    issue_category: str,
    status: str,
    runtime: ToolRuntime[SupportContext, "CustomerState"],
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
def read_ticket(runtime: ToolRuntime[SupportContext, "CustomerState"]) -> str:
    """Read the ticket details accumulated in conversation state."""
    ticket_id = runtime.state.get("ticket_id")
    if not ticket_id:
        return "No ticket has been created yet."

    return (
        f"Ticket {ticket_id}: {runtime.state.get('issue_category', 'unknown issue')}, "
        f"status {runtime.state.get('status', 'unknown')}."
    )


def get_chat_model(name: str) -> BaseChatModel:
    chat_model = init_chat_model(
        model=name,
        model_provider="openrouter",
        openrouter_api_key=openrouter_api_key,
    )
    return chat_model


def run_customer_support_demo(model: BaseChatModel) -> None:
    agent = create_agent(
        model=model,
        tools=[get_support_policy, update_ticket, read_ticket],
        system_prompt=(
            "You are a customer support agent. Use get_support_policy for customer "
            "permissions. When a customer reports an issue, use update_ticket to save "
            "the ticket. Use read_ticket when asked about an existing ticket."
        ),
        context_schema=SupportContext,
        state_schema=CustomerState,
        checkpointer=InMemorySaver(),
    )

    thread_config: RunnableConfig = {"configurable": {"thread_id": "customer-123"}}
    first_response = agent.invoke(
        {
            "messages": [
                {
                    "type": "human",
                    "content": "My order 8472 arrived damaged. Please open a delivery issue.",
                }
            ]
        },
        config=thread_config,
        context=SupportContext(user_id="user-123", customer_tier="premium"),
    )
    pprint(first_response)

    second_response = agent.invoke(
        {
            "messages": [
                {"type": "human", "content": "What is the status of my ticket?"}
            ]
        },
        config=thread_config,
        context=SupportContext(user_id="user-123", customer_tier="premium"),
    )
    pprint(second_response)


if __name__ == "__main__":
    print("Advanced Agent is running...")
    model = get_chat_model("openai/gpt-oss-120b")

    run_customer_support_demo(model)
