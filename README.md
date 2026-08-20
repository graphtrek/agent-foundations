# agent-foundations

Foundation project for building LLM agents with LangChain, using OpenRouter as the model provider.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Copy the example environment file and fill in your API key:

   ```bash
   cp .env.example .env
   ```

   Required variables:
   - `OPENROUTER_API_KEY` — your [OpenRouter](https://openrouter.ai/) API key (prompted interactively if not set).
   - `LANGCHAIN_DEBUG` — optional, set to `"true"` to enable debug prints.

## Run

Run a tutorial script with `uv run`:

```bash
uv run python src/openrouter_agent.py
```
