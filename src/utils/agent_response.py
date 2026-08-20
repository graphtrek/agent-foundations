from pprint import PrettyPrinter
from langchain.messages import HumanMessage

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