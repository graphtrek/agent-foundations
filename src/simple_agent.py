from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel, init_chat_model

from utils.agent_response import agent_response, agent_stream_response
from utils.config import load_config
from utils.tools import web_search

openrouter_api_key = load_config()

def get_model(model_name: str) -> BaseChatModel:
    return init_chat_model(
        model=model_name,
        model_provider="openrouter",
        api_key=openrouter_api_key,
        temperature=0.7,
        max_tokens=150,
        verbose=True
    )  # Initialize the chat model with the API key

def basic_agent_response(model) -> None:
    system_prompt = "You are a helpful assistant."
    model = get_model("poolside/laguna-s-2.1")

    user_prompt = "What is your last training data cutoff date? Please provide the answer in a concise manner."
    agent = create_agent(model, system_prompt=system_prompt)
    response: str = agent_response(agent, user_prompt)  # Call the agent_response function
    print(f"\nAgent Response: {response}")

def streaming_agent_response(model) -> None:
    system_prompt = "You are a Python LangChain expert. Please provide detailed and accurate information about LangChain."
    agent = create_agent(model, system_prompt=system_prompt)

    user_prompt = "What do you know about LangChain? Please provide a brief overview."
    print("\nStreaming Agent Response:")
    agent_stream_response(agent, user_prompt)  # Call the streaming response function   

def search_agent_response(model) -> None:
    system_prompt = "You are a helpful assistant that can search the web for information."
    agent = create_agent(model, tools=[web_search], system_prompt=system_prompt)

    user_prompt = "Summarize the latest AI news."
    print("\nSearch Agent Response:")
    agent_stream_response(agent, user_prompt)  # Call the streaming response function   

def main():
    model = get_model("poolside/laguna-s-2.1")
    basic_agent_response(model)  # Call the basic_agent_response function
    streaming_agent_response(model)  # Call the streaming_agent_response function
    search_agent_response(model)  # Call the search_agent_response function

if __name__ == "__main__":
    main()