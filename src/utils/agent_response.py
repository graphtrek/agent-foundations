from langchain.messages import AIMessageChunk, HumanMessage


def agent_stream_response(
    agent, prompt: list[HumanMessage], *, config: dict | None = None
) -> None:
    messages = {"messages": prompt}
    if config is not None:
        stream = agent.stream(messages, stream_mode="messages", config=config)
    else:
        stream = agent.stream(messages, stream_mode="messages")

    for token, _metadata in stream:
        if isinstance(token, AIMessageChunk) and token.content:
            print(token.content, end="", flush=True)


def agent_response(
    agent, prompt: list[HumanMessage], *, config: dict | None = None
) -> str:
    messages = {"messages": prompt}
    if config is not None:
        response = agent.invoke(messages, config=config)
    else:
        response = agent.invoke(messages)
    return response["messages"][1].content


def agent_messages(
    agent, prompt: list[HumanMessage], *, config: dict | None = None
) -> list:
    messages = {"messages": prompt}
    if config is not None:
        response = agent.invoke(messages, config=config)
    else:
        response = agent.invoke(messages)
    return response["messages"]
