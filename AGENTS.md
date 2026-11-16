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
- Run the bank branch officer chat assistant: `uv run python src/bank_officer_agent.py`.

The first three commands make OpenRouter requests. The search example also
uses DuckDuckGo, and the image example in `simple_agent.py` expects `test.jpg`
in the repository root. The MCP server uses `stdio`, so an MCP client should
launch it and communicate over standard input and output.

The planner supports `PLANNER_*`, `VISION_*`, and `TEXT_*` settings for
`MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TOP_P`, `FREQUENCY_PENALTY`,
`PRESENCE_PENALTY`, and `SEED`. Venue and catering require a vision-capable
model. Planner images are cached in `src/resources/offsite/`, conversations
are saved in `conversations/`, and logs are written to `logs/`.

The bank branch officer assistant reuses the `TEXT_*` defaults (`config.text`)
as the base model config for its coordinator, both specialists, and the
endpoint router, since none need vision; per-role tuning lives in the
`branch_coordinator.md`, `account_specialist.md`, `product_specialist.md`,
and `endpoint_specialist.md` prompt files' `yaml` blocks rather than a new
env-var family. It is an interactive, query-only demo (type `exit`, `quit`,
or `kilépés` to end the session) with three mock customers defined in
`src/utils/bank_data.py`, each with an `entitlement_tier`
(`retail`/`premium`/`business`); conversations are saved in `conversations/`
and logs are written to `logs/bank_officer_agent.log`. On every officer turn,
an endpoint-router agent (`build_endpoint_router()` in `bank_officer_agent.py`)
runs before the coordinator, matching the question to the best REST endpoint
in the mock catalog in `src/utils/endpoint_catalog.py` and recording the
result as `matched_endpoint` in `BranchState`; the coordinator's prompt uses
it to help pick a specialist, or to refuse directly when the selected
customer's entitlement tier doesn't cover the matched endpoint. Every LLM
call this example makes (coordinator, both specialists, and the endpoint
router) runs through the guardrail middleware stack from
`src/utils/guardrails.py`: a `before_model` check blocks prompt-injection/
instruction-override attempts, `PIIMiddleware` redacts emails and masks
credit card numbers on both input and output, and an `after_model` check
rewrites any reply that claims to have performed a mutating action, since
the example is query-only. The endpoint router additionally runs
`EndpointAccessMiddleware` (via `build_endpoint_router_middleware()`), which
flags `matched_endpoint.access_denied` when the selected customer's
entitlement tier is below the matched endpoint's `required_entitlement`.

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
- `src/utils/bank_data.py` holds static, dependency-free mock bank data
  (customers, accounts, transactions, products, offers) for the branch
  officer example, following the same "no business logic in the runnable
  script" split as `offsite_images.py`.
- `src/utils/endpoint_catalog.py` holds the branch officer example's static
  mock REST endpoint catalog (method, path, description, category,
  menu location, required entitlement tier) for the endpoint-router
  specialist, following the same split as `bank_data.py`. A static HTML
  mock-up of the catalog as a navigable menu lives at
  `src/resources/webapp_mockup/catalog.html` (not `index.html`, since
  `.gitignore` has an unrelated repo-wide rule for that name); it mirrors
  the catalog by hand and must be updated alongside it.
- `src/utils/guardrails.py` holds the before/after LLM-call guardrail
  middleware (`build_guardrail_middleware()`) used by the branch officer
  example; attach it via `create_agent(..., middleware=...)` on every agent
  a new example adds, the same way `bank_officer_agent.py` and
  `create_branch_tools()` do. `build_endpoint_router_middleware()` extends
  that stack with `EndpointAccessMiddleware`, the entitlement-tier access
  check used only by the endpoint router. `build_coordinator_middleware()`
  extends it with `MatchedEndpointContextMiddleware`, which the coordinator
  needs because a plain custom `AgentState` field like `matched_endpoint`
  is never automatically visible to the model - only `state["messages"]`
  and the static `system_prompt` are - so this middleware injects it into
  the system message on every coordinator model call via `wrap_model_call`.
