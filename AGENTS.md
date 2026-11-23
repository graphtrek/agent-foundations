# AGENTS.md

Foundation project for building runnable LLM-agent examples with LangChain and
LangGraph, using OpenRouter as the model provider.

## Setup & run

- Use `uv` for dependency management. Install dependencies with `uv sync`.
- Use Python `3.12` or `3.13`; the supported range is `>=3.12,<3.14`.
- Create a root `.env` file with `OPENROUTER_API_KEY`. If the key is absent,
  `load_config()` prompts for it with `getpass`.
- `LANGCHAIN_DEBUG=true` enables additional configuration and LangChain output.
- Run the introductory tutorial: `uv run python src/simple_agent/main.py`.
- Run the state-aware example: `uv run python src/advanced_agent/main.py`.
- Run the multi-agent planner: `uv run python src/offsite_planner/main.py`.
- Run the MCP server: `uv run python src/mcp_server/main.py`.
- Run the bank branch officer web chat: `uv run python src/bank_officer/main.py`,
  then open http://127.0.0.1:8050/ (`BANK_WEB_HOST`/`BANK_WEB_PORT` override
  the address).
- Run the bank branch officer terminal chat assistant:
  `uv run python src/bank_officer/terminal.py [--arch <profile id>]`
  (`BANK_ARCH` sets the default profile).
- Compare architectures on the same questions:
  `uv run python src/bank_officer/evals/run.py --arch router,no_router,single_agent [--repeat 3]`
  (cases in `src/bank_officer/evals/cases.yaml`, results in `logs/evals/`).
  The same runner (`src/bank_officer/eval_runner.py`) backs the web page
  http://127.0.0.1:8050/eval.html (`GET /api/evals/options`, `POST /api/evals`,
  `GET /api/evals/current`, `POST /api/evals/cancel`); one eval runs at a time.
  After a web run, `src/bank_officer/eval_report.py` has the Luna model
  (`EVAL_REPORT_MODEL`, default `openai/gpt-6-luna`) write a Hungarian text evaluation of
  the failed cases: which agent file of the architecture to fix and the exact change. It
  is saved as `logs/evals/<stamp>.md` and shown in a popup (button "Kiértékelés").

The first three commands make OpenRouter requests. The search example also
uses DuckDuckGo, and the image example in `simple_agent.py` expects `test.jpg`
in the repository root. The MCP server uses `stdio`, so an MCP client should
launch it and communicate over standard input and output.

The planner supports `PLANNER_*`, `VISION_*`, and `TEXT_*` settings for
`MODEL`, `TEMPERATURE`, `MAX_TOKENS`, `TOP_P`, `FREQUENCY_PENALTY`,
`PRESENCE_PENALTY`, and `SEED`. Venue and catering require a vision-capable
model. Planner images are cached in `src/offsite_planner/images/`, conversations
are saved in `conversations/`, and logs are written to `logs/`.

The bank branch officer assistant builds every agent (endpoint router,
coordinator, account, product and service specialists) from its own Markdown file in
its architecture's folder `src/bank_officer/architectures/<id>/` (`00_endpoint_router.md`,
`01_branch_coordinator.md`, `02_account_specialist.md`,
`03_product_specialist.md`, `04_service_specialist.md`), following the `dev-vault/data/agents` persona
convention: a `# Label` heading, `<!-- key: value -->` directives for model
settings, the `tools` list and the `middleware` stack, then the system prompt
body. `src/bank_officer/agent_spec.py` loads them; see that directory's `README.md`
for the format. The `TEXT_*` defaults (`config.text`) are the base model
config the files' directives override, since none of the agents need vision. It is an interactive, query-only demo (type `exit`, `quit`,
or `kilépés` to end the session) with three mock customers defined in
`src/bank_officer/bank_data.py`, each with an `entitlement_tier`
(`retail`/`premium`/`business`); conversations are saved in `conversations/`
and logs are written to `logs/bank_officer_agent.log`. On every officer turn,
an endpoint router runs before the coordinator, matching the question to the
best REST endpoint in the mock catalog in `src/bank_officer/endpoint_catalog.py` and
recording the result as `matched_endpoint` in `BranchState`. The router is
not a chat agent: it is the TypeSafe Jev decision model
(`~typesafe/jev-latest`), which OpenRouter serves only through the alpha
Decisions API (`POST /api/alpha/decisions`, not `/chat/completions`), called
by `EndpointRouter` in `src/bank_officer/decision_router.py` with one `choice`
question over the catalog (plus `none`). Below its file's `min_probability`
the answer counts as no match; a refusal, malformed answer or request error
fails closed with a fixed reply. The coordinator's prompt uses the result the coordinator's prompt uses
it to help pick a specialist. Entitlement refusals are enforced in code, not
by the prompt: when `access_denied` is true the chat loop answers with the
fixed `access_denied_reply()` and never calls the coordinator, and the
specialist wrapper tools re-check access via `check_endpoint_access()` for a
customer selected mid-turn. Every reply goes through the deterministic
`deliver_reply()` gateway, router/coordinator/specialist failures fall back to
a fixed reply, and the coordinator thread is reset when the officer switches
to a different customer so the previous customer's data leaves the context. Every chat-model
call this example makes (coordinator and all three specialists) runs through the
guardrail middleware stack from
`src/bank_officer/guardrails.py`: a `before_model` check blocks prompt-injection/
instruction-override attempts, `PIIMiddleware` redacts emails and masks
credit card numbers on both input and output, and an `after_model` check
rewrites any reply that claims to have performed a mutating action, since
the example is query-only. The Jev router has no LangChain middleware; it
runs the same checks in code (`is_prompt_injection()` and `redact_pii()` from
`guardrails.py` before the call) and sets `matched_endpoint.access_denied`
from `check_endpoint_access()`: `True` when the selected customer's
entitlement tier is below the matched endpoint's `required_entitlement`,
`None` when no customer is selected yet.

### Architecture profiles (bank officer)

The pipeline's shape is data: `src/bank_officer/architectures/<id>/architecture.yaml`
(`router`, `no_router`, `single_agent`; the folder may carry an ordering prefix, so
`03_router/` holds the profile `router`) says whether
the Jev router runs, whether the coordinator delegates to specialist
sub-agents (`mode: delegate`) or gets every data tool itself (`mode: flat`),
and each architecture folder holds its own complete copy of the agent files
(`<id>/NN_<agent>.md`), used as is - the YAML never overrides them, so a
change for one architecture is made in that folder's file. `src/bank_officer/architecture.py` validates profiles
(`validate_profile()`) and builds/caches pipelines
(`PipelineRegistry`); `tools.py` generates the `ask_<id>` wrappers from the
profile (`SpecialistBinding`, `TOOL_GROUPS`). What is mandatory stays in code:
a profile cannot override the middleware stack, and without a router the
entitlement rule still holds in the specialist gate and the tier-restricted
tools (only the code-level short-circuit is absent). The web chat has an
architecture picker (`GET /api/architectures`, `GET /api/architectures/{id}`;
`POST /api/chats` takes `{architecture}`); profiles are edited as YAML files.
Specialists are agent files in the architecture's folder; a new one needs a new file.
The `router` profile follows `bank-officer-agent-architecture-hu.html`: Luna coordinator
(`openai/gpt-6-luna`), three domain specialists the coordinator can call in
parallel, a `public_info_specialist` (tool group `public`, no customer needed: opening
hours, locations, conditions) and an `answer_synthesizer` (`coordinator.synthesizer` in
the YAML, no tools). The `ask_answer_synthesizer` tool reads the turn's specialist
answers from the graph state in code (the coordinator does not retype them); with fewer
than two answers it passes the single answer on, and an `ACCESS DENIED` answer is
returned verbatim, never merged. `no_router` and `single_agent` still give the
coordinator the general tools directly.

## Validation

There is no test suite or CI configuration yet. After Python changes, run:

```bash
uv run python -m compileall src
```

Then run the affected example when practical. Do not add committed secrets,
generated conversations, logs, or downloaded images unless the task explicitly
requires them.

## Architecture

- Each folder under `src/` is a fully self-contained example (`simple_agent/`,
  `advanced_agent/`, `offsite_planner/`, `mcp_server/`, `bank_officer/`) run as
  `uv run python src/<app>/main.py` (bank officer: `main.py` web chat, `terminal.py` terminal chat). There is
  no shared code: no `utils/` or `common/` package, and an app must never import
  from another app. If two apps need the same helper (e.g. `config.py`), each keeps
  its own copy. Imports inside an app are plain sibling imports (`from config import ...`).
- Each app loads configuration through its own `config.py`. Simple examples
  create models with `init_chat_model()`; the planner uses
  `src/offsite_planner/model_util.py` to load prompt templates and model settings
  before wrapping models with `create_agent()` from `langchain.agents`; the bank
  officer uses `get_openrouter_model()` from its own `model_util.py`.
- `src/simple_agent/agent_response.py` centralizes invoke, streaming, and full-message
  response handling. Tools live per app: `search.py` (simple_agent,
  mcp_server), `advanced_agent/tools.py`, `offsite_planner/tools.py` and
  `bank_officer/tools.py` with the specialist tool factories. Every GET endpoint in the catalog has a backing tool:
  account specialist (details, statements, business overview, scheduled
  payments), product specialist (catalog, offers, existing loans), service
  specialist (cards, card limits, loan applications, profile, support tickets)
  and customer-independent coordinator tools (`get_branch_opening_hours` with
  dates like `next_monday` via `resolve_date()`, `list_branch_locations`,
  `get_general_conditions`). Tier-restricted tools (card limits, business
  overview) re-check entitlement in code. Their data lives in `bank_data.py`
  and mirrors the fixtures in `catalog.html`. The account specialist's `summarize_spending` tool sums
  outgoing debits deterministically (excluding transfers/deposit placements);
  specialist/coordinator recursion limits are 60/80 because guardrail
  middleware nodes count as graph steps.
- Keep prompts in `src/offsite_planner/prompts/` (agent definition files for the
  bank officer example in `src/bank_officer/architectures/<id>/`, loaded by
  `src/bank_officer/agent_spec.py`) and planner image handling in
  `src/offsite_planner/offsite_images.py`; avoid embedding those assets in the runnable
  scripts.
- `src/bank_officer/bank_data.py` holds static, dependency-free mock bank data
  (customers, accounts, transactions, products, offers) for the branch
  officer example, following the same "no business logic in the runnable
  script" split as `offsite_planner/offsite_images.py`.
- `src/bank_officer/endpoint_catalog.py` holds the branch officer example's static
  mock REST endpoint catalog (method, path, description, category,
  menu location, required entitlement tier) for the endpoint-router
  specialist, following the same split as `bank_data.py`. A static HTML
  mock-up of the catalog as a navigable menu lives at
  `src/bank_officer/webapp_mockup/catalog.html` (not `index.html`, since
  `.gitignore` has an unrelated repo-wide rule for that name); it mirrors
  the catalog by hand and must be updated alongside it. Each GET item has
  a "Show test data" toggle that renders its mock response in a DataTables
  table (jQuery/DataTables from CDN) for a selectable customer, applying
  the same entitlement-tier rule; its customers, accounts, transactions,
  products and offers mirror `bank_data.py` by hand, the other fixtures
  exist only in the page.
- The branch officer turn pipeline (endpoint router, code-level access
  short-circuit, coordinator, `_deliver()` reply gateway, customer-switch
  thread reset) lives in `BranchSession` in `src/bank_officer/branch_session.py`,
  shared by the terminal loop in `bank_officer/terminal.py` and the web chat in
  `bank_officer/main.py`. `stream_turn()` yields `route`, `tool_call`,
  `tool_result`, `customer` and `reply` events. The web chat is a FastAPI
  JSON/SSE API modelled on the dev-vault chat service: `POST
  /api/chats/{id}/messages` starts the turn in a worker thread, `GET
  /api/chats/{id}/live` replays then streams its events (`src/bank_officer/live_run.py`),
  `POST .../cancel` stops it after the current step and resets the
  coordinator thread, and `DELETE /api/chats/{id}` saves the transcript to
  `conversations/`. It also serves `src/bank_officer/webapp_mockup/`, whose
  `chat.html` is the chat page (linked from `catalog.html` and back). The
  reply is sent whole, never as raw model tokens, because the PII and
  query-only guardrails act on the finished model message; tool-result
  previews go through `redact_pii()`. Sessions are in-process: one worker.
- `src/bank_officer/guardrails.py` holds the before/after LLM-call guardrail
  middleware (`build_guardrail_middleware()`) used by the branch officer
  example; attach it via `create_agent(..., middleware=...)` on every agent
  a new example adds, the same way `bank_officer/terminal.py` and
  `create_branch_tools()` do. `check_endpoint_access()` is the single
  entitlement-tier rule used by the endpoint router, the chat loop's
  short-circuit and the specialist tools. `build_coordinator_middleware()`
  extends it with `MatchedEndpointContextMiddleware`, which the coordinator
  needs because a plain custom `AgentState` field like `matched_endpoint`
  is never automatically visible to the model - only `state["messages"]`
  and the static `system_prompt` are - so this middleware injects it into
  the system message on every coordinator model call via `wrap_model_call`.
