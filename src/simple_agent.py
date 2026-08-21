from pprint import PrettyPrinter

from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel, init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

from utils.agent_response import agent_messages, agent_response, agent_stream_response
from utils.config import load_config
from utils.tools import web_search

# Load the OpenRouter API key from the configuration
openrouter_api_key = load_config()

# get_model function to initialize the chat model with the OpenRouter API key
def get_model(model_name: str) -> BaseChatModel:
    return init_chat_model(
        model=model_name,
        model_provider="openrouter",
        api_key=openrouter_api_key,
        temperature=0.7,
        max_tokens=150,
        verbose=True
    )  # Initialize the chat model with the API key

# Functions to demonstrate different types of agent responses
def basic_agent_response(model) -> None:
    system_prompt = "You are a helpful assistant."
    model = get_model("poolside/laguna-s-2.1")

    user_prompt = "What is your last training data cutoff date? Please provide the answer in a concise manner."
    agent = create_agent(model, system_prompt=system_prompt)
    response: str = agent_response(agent, user_prompt)  # Call the agent_response function
    print("---------------------------------------------------------------------------------------")
    print(f"\nAgent Response: {response}")
    print("---------------------------------------------------------------------------------------")

# Function to demonstrate streaming agent responses
def streaming_agent_response(model) -> None:
    system_prompt = "You are a Python LangChain expert. Please provide detailed and accurate information about LangChain."
    agent = create_agent(model, system_prompt=system_prompt)

    user_prompt = "What do you know about LangChain? Please provide a brief overview."
    print("---------------------------------------------------------------------------------------")
    print("\nStreaming Agent Response:")
    agent_stream_response(agent, user_prompt)  # Call the streaming response function
    print("---------------------------------------------------------------------------------------")

# Function to demonstrate agent responses with web search capabilities
def search_agent_response(model) -> None:
    system_prompt = "You are a helpful assistant that can search the web for information."
    agent = create_agent(model, tools=[web_search], system_prompt=system_prompt)

    user_prompt = "Summarize the latest AI news."
    
    response_messages = agent_messages(agent, user_prompt)  # Call the agent_messages function
    pp = PrettyPrinter(indent=4)
    print("---------------------------------------------------------------------------------------")
    print("\nSearch Agent Response Messages:")
    pp.pprint(response_messages )
    print("---------------------------------------------------------------------------------------")

# Function to demonstrate short-term memory agent responses
def shortterm_memory_agent_response(model) -> None:
    system_prompt = "You are a helpful assistant that can remember information for the duration of the conversation."
     # Specify short-term memory configuration
    agent = create_agent(model, system_prompt=system_prompt, checkpointer=InMemorySaver())

    user_prompt_1 = "Remember that my favorite color is blue."
    config = {"configurable": {"thread_id": "1"}}
    agent_response(agent, user_prompt_1, config=config)  # Store the information in memory

    user_prompt_2 = "What is my favorite color?"
    response: str = agent_response(agent, user_prompt_2, config=config)  # Retrieve the information from memory
    print("---------------------------------------------------------------------------------------")
    print(f"\nShort-term Memory Agent Response: {response}")
    print("---------------------------------------------------------------------------------------")    

# Main function to run the different agent response demonstrations
def main():
    model = get_model("poolside/laguna-s-2.1")
    basic_agent_response(model)  # Call the basic_agent_response function
    streaming_agent_response(model)  # Call the streaming_agent_response function
    search_agent_response(model)  # Call the search_agent_response function
    shortterm_memory_agent_response(model)  # Call the shortterm_memeory_agent_response function

if __name__ == "__main__":
    main()