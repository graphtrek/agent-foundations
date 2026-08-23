from dataclasses import dataclass
from pprint import pprint
from typing import Any

from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.tools import ToolRuntime, tool

from utils.config import load_config

openrouter_api_key = load_config()


@dataclass
class ColourContext:
    favorite_color: str = "blue"
    least_favorite_color: str = "green"


@tool
def get_favorite_color(runtime: ToolRuntime[ColourContext]) -> str:
    "Returns the favorite color from the runtime context."
    return runtime.context.favorite_color


@tool
def get_least_favorite_color(runtime: ToolRuntime[ColourContext]) -> str:
    "Returns the least favorite color from the runtime context."
    return runtime.context.least_favorite_color


def get_chat_model(name: str) -> Any:
    chat_model = init_chat_model(
        model=name,
        model_provider="openrouter",
        openrouter_api_key=openrouter_api_key,
    )
    return chat_model


def immutable_runtime_context(model: BaseChatModel, prompt: str) -> None:
    agent = create_agent(
        model=model,
        tools=[get_favorite_color, get_least_favorite_color],
        system_prompt="You are a helpful assistant that provides information about ColourContext in Python.",
        context_schema=ColourContext,
    )
    human_message = {"type": "human", "content": prompt}

    response = agent.invoke(
        {"messages": [human_message]},
        context=ColourContext(favorite_color="blue", least_favorite_color="green"),
    )
    pprint(response)


if __name__ == "__main__":
    print("Advanced Agent is running...")
    model = get_chat_model("openai/gpt-oss-120b")
    immutable_runtime_context(model, "What is the favorite color?")
