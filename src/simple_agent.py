from pathlib import Path
from pprint import PrettyPrinter

from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from utils.agent_response import agent_messages, agent_response, agent_stream_response
from utils.config import load_config
from utils.file_util import encode_file_to_base64
from utils.tools import web_search

SEPARATOR = "-" * 80


# Load the OpenRouter API key from the configuration
openrouter_api_key = load_config()


def get_model(model_name: str) -> BaseChatModel:
    """Create an OpenRouter chat model with the shared configuration."""
    return init_chat_model(
        model=model_name,
        model_provider="openrouter",
        api_key=openrouter_api_key,
        temperature=0.7,
        max_tokens=150,
        verbose=True,
    )


# Functions to demonstrate different types of agent responses
def basic_agent_response(model: BaseChatModel) -> None:
    system_prompt = "You are a helpful assistant."

    user_prompt = [
        HumanMessage(
            content=(
                "What is your last training data cutoff date? "
                "Please provide the answer in a concise manner."
            )
        )
    ]
    agent = create_agent(model=model, system_prompt=system_prompt)
    response: str = agent_response(agent, user_prompt)
    print(SEPARATOR)
    print(f"\nAgent Response: {response}")
    print(SEPARATOR)


# Function to demonstrate streaming agent responses
def streaming_agent_response(model: BaseChatModel) -> None:
    system_prompt = (
        "You are a Python LangChain expert. "
        "Please provide detailed and accurate information about LangChain."
    )
    agent = create_agent(model=model, system_prompt=system_prompt)

    user_prompt = [
        HumanMessage(
            content=(
                "What do you know about LangChain? Please provide a brief overview."
            )
        )
    ]
    print(SEPARATOR)
    print("\nStreaming Agent Response:")
    agent_stream_response(agent, user_prompt)
    print(SEPARATOR)


# Function to demonstrate agent responses with web search capabilities
def search_agent_response(model: BaseChatModel) -> None:
    system_prompt = (
        "You are a helpful assistant that can search the web for information."
    )
    agent = create_agent(model=model, tools=[web_search], system_prompt=system_prompt)

    user_prompt = [HumanMessage(content="Summarize the latest AI news.")]

    response_messages = agent_messages(agent, user_prompt)
    pp = PrettyPrinter(indent=4)
    print(SEPARATOR)
    print("\nSearch Agent Response Messages:")
    pp.pprint(response_messages)
    print(SEPARATOR)


# Function to demonstrate short-term memory agent responses
def shortterm_memory_agent_response(model: BaseChatModel) -> None:
    system_prompt = (
        "You are a helpful assistant that can remember information "
        "for the duration of the conversation."
    )
    agent = create_agent(
        model=model, system_prompt=system_prompt, checkpointer=InMemorySaver()
    )

    user_prompt_1 = [HumanMessage(content="Remember that my favorite color is blue.")]
    config = {"configurable": {"thread_id": "color_memory_thread"}}
    agent_response(agent, user_prompt_1, config=config)

    user_prompt_2 = [HumanMessage(content="What is my favorite color?")]
    response: str = agent_response(agent, user_prompt_2, config=config)
    print(SEPARATOR)
    print(f"\nShort-term Memory Agent Response: {response}")
    print(SEPARATOR)


def image_analysis_agent_response(model: BaseChatModel) -> None:
    system_prompt = (
        "You are an image analysis assistant that can analyze images "
        "and provide insights."
    )
    agent = create_agent(model=model, system_prompt=system_prompt)

    image_path = Path(__file__).resolve().parent.parent / "test.jpg"
    image_base64 = encode_file_to_base64(str(image_path))

    user_prompt = [
        HumanMessage(
            content=[
                {"type": "text", "text": "Tell me about this image"},
                {"type": "image", "base64": image_base64, "mime_type": "image/jpeg"},
            ]
        )
    ]

    response: str = agent_response(agent, user_prompt)
    print(SEPARATOR)
    print(f"\nImage Analysis Agent Response: {response}")
    print(SEPARATOR)


# Main function to run the different agent response demonstrations
def main() -> None:

    # Choosing an LLM is like hiring: more experienced/qualified models (like senior
    # contractors) cost more, priced per token instead of per hour.
    text_model = get_model("poolside/laguna-s-2.1")

    # Now that we hired our contractor, the simplest task is one question expecting
    # a direct answer, e.g. asking for the model's training cut-off date.
    basic_agent_response(text_model)

    # We want the answer word by word, like talking to a person, so we can read it
    # as it arrives instead of waiting for the whole response.
    streaming_agent_response(text_model)

    # For the latest news our contractor needs a web search tool (DuckDuckGo here,
    # like a Google search) to go out and look things up on the internet.
    search_agent_response(text_model)

    # So far every call was a one-off Q&A with no memory of prior turns. Real
    # conversations need our contractor to remember, e.g. we tell it our favorite
    # color then ask about it later; without memory it simply wouldn't know. Short-term
    # memory takes our communication to the next level.
    shortterm_memory_agent_response(text_model)

    # Time to hire a different contractor: Gemma from Google can analyze images as
    # well as text, while our laguna model is great at text but clueless about images.
    # We need to carefully pick the best model for the specific problem at hand.
    image_text_model = get_model("google/gemma-4-26b-a4b-it")
    image_analysis_agent_response(image_text_model)


if __name__ == "__main__":
    main()
