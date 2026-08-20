# AGENTS.md

Foundation project for building LLM agents with LangChain, using OpenRouter as the model provider.

## Setup & run

- Dependency manager is `uv` (not pip/poetry). Install deps: `uv sync`.
- Run a script: `uv run python src/openrouter_agent.py`.
- Requires a `.env` file in the project root (not committed) with:
  - `OPENROUTER_API_KEY` — required; prompted interactively via `getpass` if missing.
  - `LANGCHAIN_DEBUG` — optional, set to `"true"` to enable debug prints.
  - `PINECON_API_KEY` / `PINECON_ENV` — for Pinecone vector store experiments.
- Python requirement: `>=3.12,<3.14` (see [pyproject.toml](pyproject.toml)).

## Architecture

- Each `src/*.py` file is a standalone runnable tutorial script (no shared package structure yet).
- Common pattern in these scripts, e.g. [src/openrouter_agent.py](src/openrouter_agent.py):
  - `load_config()` loads `.env` and resolves the API key.
  - Build a model with `init_chat_model(model=..., model_provider="openrouter", api_key=...)`.
  - Wrap it with `create_agent(model=...)` from `langchain.agents`.
  - Stream responses via `agent.stream(messages, stream_mode="messages")`, printing tokens as they arrive.
- No test suite or CI configured yet.
