# AGENTS.md

Foundation project for building runnable LLM-agent examples with LangChain and
LangGraph, using OpenRouter as the model provider.

## Setup & run

- Use `uv` for dependency management. Install dependencies with `uv sync`.
- Use Python `3.12` or `3.13`; the supported range is `>=3.12,<3.14`.
- Create a root `.env` file with `OPENROUTER_API_KEY`. If the key is absent,
  `load_config()` prompts for it with `getpass`.
- `LANGCHAIN_DEBUG=true` enables additional configuration and LangChain output.
- Run the introductory tutorial: `uv run python src/simple_agent.py`.
- Run the state-aware example: `uv run python src/advanced_agent.py`.
- Run the multi-agent planner: `uv run python src/corporate_offsite_planner_agent.py`.
- Run the MCP server: `uv run python src/mcp_server.py`.

The first three commands make OpenRouter requests. The search example also
uses DuckDuckGo, and the image example in `simple_agent.py` expects `test.jpg`
in the repository root. The MCP server uses `stdio`, so an MCP client should
launch it and communicate over standard input and output.

The planner supports `PLANNER_*`, `VISION_*`, and `TEXT_*` settings for
`MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TOP_P`, `FREQUENCY_PENALTY`,
`PRESENCE_PENALTY`, and `SEED`. Venue and catering require a vision-capable
model. Planner images are cached in `src/resources/offsite/`, conversations
are saved in `conversations/`, and logs are written to `logs/`.

## Validation

There is no test suite or CI configuration yet. After Python changes, run:

```bash
uv run python -m compileall src
```

Then run the affected example when practical. Do not add committed secrets,
generated conversations, logs, or downloaded images unless the task explicitly
requires them.

## Architecture

- Each `src/*.py` file is a standalone runnable example, with shared helpers in
  `src/utils/` and prompts in `src/resources/prompts/`.
- Common configuration is loaded through `src/utils/config.py`. Simple
  examples create models with `init_chat_model()`; the planner uses
  `src/utils/model_util.py` to load prompt templates and model settings before
  wrapping models with `create_agent()` from `langchain.agents`.
- `src/utils/agent_response.py` centralizes invoke, streaming, and full-message
  response handling. `src/utils/tools.py` contains the search and specialist
  tool factories.
- Keep prompts in `src/resources/prompts/` and planner image handling in
  `src/utils/offsite_images.py`; avoid embedding those assets in the runnable
  scripts.
