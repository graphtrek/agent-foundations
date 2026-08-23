# agent-foundations

Small, runnable examples for learning how to build LLM agents with
[LangChain](https://python.langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/).
The examples use [OpenRouter](https://openrouter.ai/) as the model provider and
show how an agent can answer normally, stream output, call a tool, remember
messages for a conversation, and analyze an image.

The project is intentionally split into simple Python files. Read
`src/simple_agent.py` first, then follow its imports into `src/utils/`.

## Prerequisites

- Python `3.12` or `3.13`
- [uv](https://docs.astral.sh/uv/) for installing dependencies
- An OpenRouter API key
- Internet access for OpenRouter and DuckDuckGo searches

## Setup

Install the dependencies from `pyproject.toml`:

```bash
uv sync
```

Create a `.env` file in the project root and add your key:

```dotenv
OPENROUTER_API_KEY=your-openrouter-api-key
LANGCHAIN_DEBUG=false
```

`OPENROUTER_API_KEY` is required by the chat model. If it is missing, the
example asks for it interactively without displaying the key on screen.
`LANGCHAIN_DEBUG=true` enables extra debug output from the configuration
helper and LangChain components.

## Run the examples

Run the main tutorial with:

```bash
uv run python src/simple_agent.py
```

The script runs all demonstrations in sequence. The image example expects a
JPEG at `test.jpg` in the project root. Add an image there before running that
example, or temporarily comment out the `image_analysis_agent_response` call
in `main()` while learning about the other examples.

To run the MCP server example:

```bash
uv run python src/mcp_server.py
```

This server uses MCP's `stdio` transport, so an MCP client should launch the
process and communicate through standard input and output. The configured
host and port are displayed for visibility, but the selected transport is
`stdio`.

## Project structure

```text
src/
├── simple_agent.py          # Main LangChain agent demonstrations
├── mcp_server.py            # MCP server with a search tool and GitHub resource
└── utils/
      ├── agent_response.py    # Helpers for invoke and stream response formats
      ├── config.py            # Loads environment variables and the API key
      ├── file_util.py         # Encodes local files for multimodal messages
      └── tools.py             # LangChain web-search tool
```

## Python files explained

### `src/simple_agent.py`

This is the main tutorial script and the best starting point. It demonstrates
the normal lifecycle of a LangChain agent:

1. Load configuration with `load_config()`.
2. Create a chat model with `init_chat_model()`.
3. Turn the model into an agent with `create_agent()`.
4. Send `HumanMessage` objects to the agent.
5. Read the returned messages, either all at once or as a stream.

The `get_model()` function centralizes model creation. It receives a model
name, selects the `openrouter` provider, and applies generation settings such
as temperature and maximum output tokens. Returning `BaseChatModel` keeps the
rest of the file independent of one concrete provider class.

The demonstration functions are:

- `basic_agent_response(model)`: creates a simple assistant agent and uses
   `agent_response()` to retrieve a final text answer from `agent.invoke()`.
- `streaming_agent_response(model)`: uses `agent.stream(...,
   stream_mode="messages")` so `AIMessageChunk` objects can be printed as they
   arrive. Streaming improves perceived responsiveness for longer answers.
- `search_agent_response(model)`: registers the `web_search` tool. The agent
   can decide to call DuckDuckGo before producing an answer. This function uses
   `agent_messages()` so you can inspect the complete message and tool-call
   history with `PrettyPrinter`.
- `shortterm_memory_agent_response(model)`: supplies an
   `InMemorySaver` checkpointer. The same `thread_id` in the config identifies
   the conversation, allowing the second request to retrieve the favorite
   color from the first request. This memory is temporary and disappears when
   the process stops.
- `image_analysis_agent_response(model)`: reads `test.jpg`, converts it to
   base64, and sends a multimodal `HumanMessage` containing both text and an
   image. This requires a model that supports image input.

`main()` chooses text and image-capable models and runs the examples. The
`if __name__ == "__main__":` guard means `main()` runs when this file is
executed directly, but not when the module is imported by another script.

### `src/utils/config.py`

This module owns environment and secret loading. `load_config()` uses
`find_dotenv()` to locate `.env`, calls `load_dotenv()` to place its values in
`os.environ`, and returns `OPENROUTER_API_KEY`.

If the key is not present, `getpass.getpass()` requests it without echoing the
secret. The key is then placed in the current process environment so model
initialization can use it. Keeping this behavior in one function avoids
duplicating configuration code across tutorial scripts.

### `src/utils/agent_response.py`

This module hides the low-level LangGraph response shapes used by agents:

- `agent_response()` calls `agent.invoke()` and returns the assistant's text.
- `agent_messages()` calls `agent.invoke()` and returns the full `messages`
   list, including human messages, assistant messages, and tool messages.
- `agent_stream_response()` calls `agent.stream()` and prints each non-empty
   `AIMessageChunk` immediately.

Each helper accepts an optional `config` dictionary. Passing the config is
important for checkpointer-backed conversations because it carries the
`thread_id` that selects the conversation state.

The type annotation `list[HumanMessage]` describes the expected input, while
the dictionary `{"messages": prompt}` is the state shape expected by the
created agent.

### `src/utils/tools.py`

This module turns DuckDuckGo search into a LangChain tool. The `@tool`
decorator converts `web_search()` into an object with a name, description,
input schema, and an `invoke()` method that an agent can use.

The function accepts a plain string query and delegates the actual search to
`DuckDuckGoSearchResults`. Its docstring becomes part of the tool description,
which helps the model decide when the tool is relevant. Tools should have
clear names, useful docstrings, and focused inputs so an agent can use them
reliably.

### `src/utils/file_util.py`

`encode_file_to_base64()` is a small file-processing helper used by the image
example. It opens a path in binary mode (`"rb"`), reads the bytes, encodes
them with Python's standard-library `base64` module, and decodes the result to
text.

Base64 allows binary file content to be placed in a message payload. The
function does not validate file existence or MIME type, so callers are
responsible for supplying a valid path and the correct MIME type in the
message.

### `src/mcp_server.py`

This file exposes related capabilities through the
[Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It creates a
`FastMCP` server named `LangChain Agent Server` and defines three MCP features:

- `search_web()` is an MCP tool that searches DuckDuckGo.
- `search_prompt()` is an MCP prompt template that limits the assistant's
   subject area to LangChain, LangGraph, and LangSmith and explains which
   tools/resources are available.
- `resource()` is an MCP resource registered under a GitHub-style URI. It
   downloads the `README.md` file from the `langchain-mcp-adapters` repository,
   raises an error for unsuccessful HTTP responses, and returns a readable
   error string when the request fails.

The decorators `@mcp.tool()`, `@mcp.prompt()`, and `@mcp.resource(...)` register
Python functions with the MCP server. The `__main__` block starts the server
with `mcp.run(transport="stdio")`.

## LangChain concepts in this repository

### Models and agents

`init_chat_model()` creates a chat model abstraction. `create_agent()` adds an
agent loop around that model. When tools are available, the loop can decide
whether to call a tool, read its result, and then continue toward a final
answer.

### Messages

The examples use `HumanMessage` for user input and inspect
`AIMessageChunk` during streaming. An agent's returned state contains a
`messages` list, which is useful when debugging tool calls or understanding
what the model actually produced.

### Short-term memory

`InMemorySaver` stores checkpoints only in process memory. A stable
`thread_id` groups requests into one conversation. For production
applications, use a durable checkpointer or database instead of relying on
this tutorial-only storage.

### Tools versus MCP tools

`src/utils/tools.py` creates a tool directly for a LangChain agent. In
contrast, `src/mcp_server.py` publishes tools, prompts, and resources through
MCP so a compatible external client can discover and use them. The underlying
search capability is similar, but the integration boundary is different.

## Learning path

1. Run the basic response and inspect `agent_response()`.
2. Compare `invoke()` with streaming in `agent_stream_response()`.
3. Run the search example and inspect the full message list.
4. Change the `thread_id` in the memory example and observe that a new thread
    has no previous conversation.
5. Add an image and trace the multimodal message in the image example.
6. Run the MCP server and connect it to an MCP-compatible client.
