from pprint import PrettyPrinter

from langchain.messages import AIMessageChunk, HumanMessage


def agent_stream_response(agent, prompt: str, *, config: dict | None = None) -> None:
    messages = {"messages": [HumanMessage(content=prompt)]}
    # response_metadata = None  # Enable streaming in metadata
    if config is not None:
        for token, metadata in agent.stream(messages, stream_mode="messages", config=config):
            # response_metadata = metadata  # Update response metadata with each token
            if isinstance(token, AIMessageChunk) and token.content:  # Check if there's actual content
                print(token.content, end="", flush=True)  # Print token
    else:
        for token, metadata in agent.stream(messages, stream_mode="messages"):
            # response_metadata = metadata  # Update response metadata with each token
            if isinstance(token, AIMessageChunk) and token.content:  # Check if there's actual content
                print(token.content, end="", flush=True)  # Print token
    
    # print("\nResponse Metadata:")
    # Print the final response metadata
    # pp = PrettyPrinter(indent=4)
    # pp.pprint(response_metadata) 

def agent_response(agent, prompt: str, *, config: dict | None = None) -> str:
    messages = {"messages": [HumanMessage(content=prompt)]}
    if config is not None:
        response = agent.invoke(messages, config=config)
    else:
        response = agent.invoke(messages)
    return response['messages'][1].content # Return the content of the response

def agent_messages(agent, prompt: str, *, config: dict | None = None) -> list:
    messages = {"messages": [HumanMessage(content=prompt)]}
    if config is not None:
        response = agent.invoke(messages, config=config)
    else:
        response = agent.invoke(messages)
    return response['messages']  # Return the content and metadata of the response