import os
import getpass
from urllib import response
from dotenv import load_dotenv, find_dotenv
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from pprint import PrettyPrinter
from langchain.messages import HumanMessage, AIMessage, SystemMessage

def load_config() -> str:
    env_path = find_dotenv()
    if env_path:
        print(f"Loading environment variables from: {env_path}")
        load_dotenv(env_path)
    else:
        print("No .env file found. Please ensure that the .env file exists in the project directory.")      

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key is None:
        print("Please enter your OpenRouter API key:")
        api_key = getpass.getpass("API Key: ")
        os.environ["OPENROUTER_API_KEY"] = api_key

    if api_key and api_key.strip():
        print(f'OPENROUTER_API_KEY environment variable is set to: {api_key}')
    else:
        print("OPENROUTER_API_KEY environment variable is not set.")

    if os.environ.get("LANGCHAIN_DEBUG") == "true":
        print("LANGCHAIN_DEBUG is set to true. Debugging information will be printed.")
    return api_key

def simple_agent(model_name: str):
    api_key = load_config()
    model_simple = init_chat_model(
        model=model_name,
        model_provider="openrouter",
        api_key=api_key,
        temperature=0.7,
        max_tokens=150,
        verbose=True
    )  # Initialize the chat model with the API key

    agent_simple = create_agent(model=model_simple)
    return agent_simple

def stream_agent(agent, prompt: str):
    messages = {"messages": [HumanMessage(content=prompt)]}
    response_metadata = None  # Enable streaming in metadata
    for token, metadata in agent.stream(messages, stream_mode="messages"):
        response_metadata = metadata  # Update response metadata with each token
        if token.content:  # Check if there's actual content
            print(token.content, end="", flush=True)  # Print token
    pp = PrettyPrinter(indent=4)
    print("\n\nResponse Metadata:")
    pp.pprint(response_metadata) # Print the final response metadata

def main():
    agent = simple_agent("poolside/laguna-s-2.1:free")
    prompt = "What is your last training data cutoff date? Please provide the answer in a concise manner."
    stream_agent(agent, prompt)

if __name__ == "__main__":
    main()