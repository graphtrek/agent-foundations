from pprint import pprint

from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from utils.config import load_config
from utils.tools import CustomerState, SupportContext, create_customer_support_tools

openrouter_api_key = load_config().openrouter_api_key


def get_chat_model(name: str) -> BaseChatModel:
    chat_model = init_chat_model(
        model=name,
        model_provider="openrouter",
        openrouter_api_key=openrouter_api_key,
    )
    return chat_model


def run_customer_support_demo(model: BaseChatModel) -> None:
    support_tools = create_customer_support_tools()
    agent = create_agent(
        model=model,
        tools=support_tools,
        system_prompt=(
            "You are a customer support agent. Use get_support_policy for customer "
            "permissions. When a customer reports an issue, use update_ticket to save "
            "the ticket. Use read_ticket when asked about an existing ticket."
        ),
        context_schema=SupportContext,
        state_schema=CustomerState,
        checkpointer=InMemorySaver(),
        middleware=[],
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
