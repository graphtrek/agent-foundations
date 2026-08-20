from langchain.agents import create_agent
from langchain.chat_models import init_chat_model

from utils.agent_response import agent_response, agent_stream_response
from utils.config import load_config

openrouter_api_key = load_config()

def simple_agent(model_name: str, system_prompt: str) -> object:
    model_simple = init_chat_model(
        model=model_name,
        model_provider="openrouter",
        api_key=openrouter_api_key,
        temperature=0.7,
        max_tokens=150,
        verbose=True
    )  # Initialize the chat model with the API key

    return create_agent(model=model_simple, system_prompt=system_prompt)  # Create and return the agent

def basic_agent_response() -> None:
    model_name = "poolside/laguna-s-2.1"
    system_prompt = "You are a helpful assistant."
    agent = simple_agent(model_name, system_prompt)

    user_prompt = "What is your last training data cutoff date? Please provide the answer in a concise manner."
    response: str = agent_response(agent, user_prompt)
    print(f"\nAgent Response: {response}")

def streaming_agent_response() -> None:
    model_name = "poolside/laguna-s-2.1"
    system_prompt = "You are a Python LangChain expert. Please provide detailed and accurate information about LangChain."
    agent = simple_agent(model_name, system_prompt)

    user_prompt = "What do you know about LangChain? Please provide a brief overview."
    print("\nStreaming Agent Response:")
    agent_stream_response(agent, user_prompt)  # Call the streaming response function   
    
def main():
    basic_agent_response() 
    streaming_agent_response()  # Call the streaming_agent_response function

if __name__ == "__main__":
    main()