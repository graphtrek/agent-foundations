# agent-foundations

Small, runnable examples for learning how to build LLM agents with
[LangChain](https://python.langchain.com/) and [LangGraph](https://langchain-ai.github.io/langgraph/).
The examples use [OpenRouter](https://openrouter.ai/) as the model provider and
show how an agent can answer normally, stream output, call a tool, remember
messages for a conversation, and analyze an image.

The project is intentionally split into simple Python files. Read
`src/simple_agent.py` first, then follow its imports into `src/utils/`. Once the
basics are clear, move on to `src/advanced_agent.py` for runtime context and
state-aware tools.

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

The scripts load `.env` from the project root even when they are launched from
`src/`. Do not commit `.env`; the key is used only by the current process.

## Run the examples

Run the main tutorial with:

```bash
uv run python src/simple_agent.py
```

The script runs all demonstrations in sequence. The image example expects a
JPEG at `test.jpg` in the project root. Add an image there before running that
example, or temporarily comment out the `image_analysis_agent_response` call
in `main()` while learning about the other examples.

Run the advanced customer-support example with:

```bash
uv run python src/advanced_agent.py
```

This example shows how tools read a typed runtime context and read/write
conversation state across turns.

Run the multi-agent corporate offsite planner with:

```bash
uv run python src/corporate_offsite_planner_agent.py
```

The planner coordinates three specialist agents: vision models select a venue
and catering option from generated example images, while a text model drafts
the agenda. The coordinator combines their results into a final proposal and
prints the complete conversation. Images are cached under
`src/resources/offsite/`; the conversation is saved under `conversations/`,
and runtime logs are written to `logs/corporate_offsite_planner.log`.

The planner has defaults for all three models, but each can be overridden in
`.env`:

```dotenv
PLANNER_MODEL=openai/gpt-oss-120b
VISION_MODEL=google/gemma-4-26b-a4b-it
TEXT_MODEL=poolside/laguna-s-2.1
PLANNER_TEMPERATURE=0.7
PLANNER_MAX_TOKENS=900
VISION_TEMPERATURE=0.3
VISION_MAX_TOKENS=500
TEXT_TEMPERATURE=0.7
TEXT_MAX_TOKENS=500
LOG_LEVEL=INFO
```

Each model also accepts optional `TOP_P`, `FREQUENCY_PENALTY`,
`PRESENCE_PENALTY`, and `SEED` settings using the same prefix. The planner
requires a model with vision support for the venue and catering specialists.

To run the MCP server example:

```bash
uv run python src/mcp_server.py
```

This server uses MCP's `stdio` transport, so an MCP client should launch the
process and communicate through standard input and output. The configured
host and port are displayed for visibility, but the selected transport is
`stdio`.

## Validation

There is no automated test suite yet. Check the Python sources and imports with:

```bash
uv run python -m compileall src
```

For a behavior check, run the example that you changed. The agent examples
make model requests; the search and image examples also need their external
service or local image input.

## Project structure

```text
src/
├── simple_agent.py          # Main LangChain agent demonstrations
├── advanced_agent.py        # Runtime context and state-aware tools
├── corporate_offsite_planner_agent.py  # Multi-agent offsite planner
├── mcp_server.py            # MCP server with a search tool and GitHub resource
├── resources/
│     ├── prompts/            # Specialist and coordinator system prompts
│     └── offsite/             # Cached venue and catering images
└── utils/
      ├── agent_response.py    # Helpers for invoke and stream response formats
      ├── config.py            # Loads environment variables and the API key
      ├── conversation_util.py  # Formats and saves planner conversations
      ├── file_util.py         # Encodes local files for multimodal messages
      ├── model_util.py         # Loads prompt templates and configured models
      ├── offsite_images.py    # Downloads and caches planner images
      └── tools.py             # LangChain web-search and planner tools
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

### `src/advanced_agent.py`

This script builds on `simple_agent.py` and demonstrates two features that
matter for real applications: a typed runtime context and mutable conversation
state.

`SupportContext` is a dataclass passed to `agent.invoke(..., context=...)`. It
carries per-request data such as the user id and customer tier. Tools read it
through `ToolRuntime[SupportContext]`. The context is immutable for the run:
tools only read `runtime.context`, so this data stays deterministic and
verifiable instead of being inferred from free-form model text. It is also kept
out of the conversation messages, which suits secrets like auth tokens.

`CustomerState` extends `AgentState` with extra keys (`ticket_id`,
`issue_category`, `status`). Unlike the context, state is mutable: a tool can
return a `Command(update=...)` to write into it, and later tools read it back.

The tools are:

- `get_support_policy(runtime)`: reads the typed context and returns a policy
   string for the current customer.
- `update_ticket(...)`: writes ticket fields into state by returning a
   `Command` and appends a `ToolMessage` acknowledging the change.
- `read_ticket(runtime)`: reads the ticket fields previously stored in state.

`run_customer_support_demo(model)` creates the agent with `context_schema`,
`state_schema`, and an `InMemorySaver` checkpointer, then runs two turns on the
same `thread_id`. The first turn opens a ticket; the second asks for its status
and reads it back from state, showing how context, state, and short-term memory
work together.

Because `@tool` evaluates type hints eagerly, `CustomerState` is defined before
the tools that reference it, and `thread_config` is annotated as
`RunnableConfig` so the type checker accepts it.

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

### Runtime context versus state

`src/advanced_agent.py` shows the difference between two ways to give tools
data beyond the chat messages. Runtime context (`context_schema`) is passed per
`invoke()` call and is read-only for the run, which suits request-scoped values
like user ids, tiers, or auth tokens. State (`state_schema`) is mutable: tools
write to it by returning a `Command(update=...)`, and it is persisted by the
checkpointer so later turns can read it back.

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
6. Run `advanced_agent.py` and trace how context stays fixed while state changes
    across the two turns.
7. Run `corporate_offsite_planner_agent.py` and inspect the specialist tool
   calls, image links, saved conversation, and log.
8. Run the MCP server and connect it to an MCP-compatible client.

### `src/corporate_offsite_planner_agent.py`

This example demonstrates a coordinator agent that delegates a business task
to focused specialists. The coordinator first records the request in typed
state, then calls venue, catering, and agenda tools. Those tools invoke
specialist agents with separate prompts and models. The coordinator validates
that the required tools ran and retries an incomplete response up to three
times before saving the conversation.

The example is intentionally self-contained: `utils/offsite_images.py`
downloads a small set of source images on first use and reuses the local files
afterward. The specialist prompts live in `src/resources/prompts/`, where their
model settings and system instructions can be reviewed or changed.
