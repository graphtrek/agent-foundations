# AGENTS.md

Foundation project for building LLM agents with LangChain, using OpenRouter as the model provider.

## Setup & run

- Dependency manager is `uv` (not pip/poetry). Install deps: `uv sync`.
- Run the introductory tutorial: `uv run python src/simple_agent.py`.
- Run the state-aware example: `uv run python src/advanced_agent.py`.
- Run the multi-agent planner: `uv run python src/corporate_offsite_planner_agent.py`.
- Run the MCP server: `uv run python src/mcp_server.py`.
- Requires a `.env` file in the project root (not committed) with:
  - `OPENROUTER_API_KEY` — required; prompted interactively via `getpass` if missing.
  - `LANGCHAIN_DEBUG` — optional, set to `"true"` to enable debug prints.
- The offsite planner also supports `PLANNER_*`, `VISION_*`, and `TEXT_*`
  model settings, including `MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TOP_P`,
  `FREQUENCY_PENALTY`, `PRESENCE_PENALTY`, and `SEED`.
- Python requirement: `>=3.12,<3.14` (see [pyproject.toml](pyproject.toml)).

## Architecture

- Each `src/*.py` file is a standalone runnable example, with shared helpers in
  `src/utils/` and prompts in `src/resources/prompts/`.
- Common model setup loads configuration through `src/utils/config.py`, creates
  OpenRouter models with `init_chat_model()` or `load_configured_model()`, and
  wraps them with `create_agent()` from `langchain.agents`.
- The planner generates or reuses images in `src/resources/offsite/`, saves
  conversations in `conversations/`, and writes logs to `logs/`.
- No test suite or CI is configured yet.
