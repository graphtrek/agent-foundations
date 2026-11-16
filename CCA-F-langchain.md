# Claude Certified Architect Foundation Exam: LangChain / LangGraph Edition

Companion to `CCA-F.md`. Same structure, but every Anthropic SDK / Claude Code
concept is mapped to its LangChain 1.x / LangGraph equivalent. The principles
(deterministic over fuzzy, control the loop, isolate context) are provider
independent. The names, fields and APIs are not.

> Verified against docs.langchain.com (Python pages) on 2026-11-15.
> Items marked **[unverified]** were not confirmed in the docs and come from
> general knowledge. Project pins: `langchain 1.3.15`, `langgraph 1.2.11`.

## 0. The Exam Deconstructed

The exam itself is Anthropic specific. This file only re-maps the topics.

| Domain | Topic                                  | LangChain counterpart                         |
| ------ | -------------------------------------- | --------------------------------------------- |
| 1.     | Agentic Architecture & Orchestration   | `create_agent`, LangGraph, subagents          |
| 2.     | Tool Design & MCP Integration          | `@tool`, MCP adapter                          |
| 3.     | Claude Code Configuration & Workloads  | no direct equivalent (Deep Agents CLI is the closest) |
| 4.     | Prompt Engineering & Structured Output | `response_format`                             |
| 5.     | Context Management & Reliability       | checkpointers, summarization/retry middleware |

Rule stays the same: when unsure, pick the most deterministic and controlled answer.

## 1. Agentic Architecture & Orchestration

### 1.1 Agentic Loops and Core API

    Agentic loop: Plan -> Act -> Observe -> Decide -> Repeat
    Anthropic SDK:  you write the while loop around client.messages.create()
    LangChain:      create_agent() runs the loop for you (built on LangGraph)

Per the docs: the loop calls a model, lets it choose tools to execute, and
**finishes when it calls no more tools**.

| Anthropic Messages API        | LangChain                                                     |
| ----------------------------- | ------------------------------------------------------------- |
| `stop_reason == "tool_use"`   | `AIMessage.tool_calls` is not empty                           |
| `stop_reason == "end_turn"`   | `AIMessage.tool_calls` is empty -> loop ends                  |
| `max_tokens`, `refusal` ...   | only in `AIMessage.response_metadata`, provider specific      |
| `tool_result` in a user msg   | `ToolMessage(content=..., tool_call_id=...)`                  |
| loop guard                    | `recursion_limit` in the run config (see below)               |

    LangChain normalizes tool calls (AIMessage.tool_calls), NOT stop reasons.
    Raw reason keys seen in the docs examples:
        Azure/OpenAI:       response_metadata["finish_reason"]
        Google GenAI:       response_metadata["finishReason"]
        Bedrock Converse:   response_metadata["stopReason"]
        Anthropic:          "stop_reason" [unverified]
    Do not write business logic on these keys if the provider can change.

Recursion limit (verified):
- Caps **super-steps** per run, not model calls. One tool round trip is more than one step.
- On exceed LangGraph raises `GraphRecursionError`.
- Python default is 10,007 super-steps since langgraph 1.1.4 (JavaScript default is 25).
- Set it as a top-level config key, not under `configurable`:
  `agent.invoke(input, {"recursion_limit": 25})`.
- A tight limit is the deterministic loop guard. The huge default is not one.

### 1.2 Multi Agent Orchestration

    Hub and spoke: all communication goes through the orchestrator.
    Sub-agents never talk to each other.
        - context isolation
        - focused tools
        - parallel execution
        - failure isolation

| Claude Code / Anthropic        | LangChain                                                     |
| ------------------------------ | ------------------------------------------------------------- |
| Task tool (isolated sub-agent) | **subagents pattern**: sub-agent wrapped as a `@tool`         |
| only orchestrator has Task     | only the supervisor agent gets the sub-agent tools            |
| orchestrator sees summary only | the tool returns only the sub-agent final message             |
| parallel in one response       | several tool calls in one model turn [unverified]             |
| agent handoff                  | **handoffs pattern** (verified): a tool updates a state variable (`current_step` / `active_agent`) and the system switches config or agent; the active agent talks to the user directly, NOT hub and spoke. The term was coined by OpenAI |

Verified details:
- Two tool patterns in the docs: **tool per agent** (fine-grained control) and
  **single dispatch tool** (many agents, less per-agent customization).
- The docs example returns `result["messages"][-1].text`, so the supervisor
  never sees the sub-agent's intermediate reasoning or tool calls. That is the
  context isolation point.
- Tool descriptions decide when the supervisor picks a sub-agent, so write them
  as precisely as in 2.1.

Session operations (verified against LangGraph persistence docs):

    thread_id identifies saved state.
    new input, same thread_id    -> appended to the thread state, run starts from the entry point
    invoke(None, config)         -> continue after an error (retries unfinished work)
    invoke(Command(resume=x))    -> answer an interrupt()
    new thread_id                -> empty state
    fork (time travel)           -> pick a snapshot from get_state_history(config),
                                    update_state(snapshot.config, values) -> fork_config,
                                    invoke(None, fork_config)
                                    the original checkpoints stay in history, like a git branch

Warning from the docs: replaying a checkpoint can run tools and API calls again.
It does not undo earlier external effects (sent messages, database writes).

NOTE: "resume the same thread_id" in the original notes (Claude Code `--resume`)
is NOT the same as reusing a `thread_id` here.

### 1.3 Hooks: Programmatic Enforcement

    Deterministic code before/after the model or tool call.
    If a rule must be 100% enforced, use code, not a prompt.

LangChain agent middleware hooks (verified): `before_agent`, `before_model`,
`wrap_model_call`, `wrap_tool_call`, `after_model`, `after_agent`.

| Claude Code hook      | LangChain middleware                                         |
| --------------------- | ------------------------------------------------------------ |
| `PreToolUse`          | `wrap_tool_call` (before calling the handler) or `after_model` (tool calls exist, none executed yet) |
| `PostToolUse`         | `wrap_tool_call` (after the handler returns)                 |
| `UserPromptSubmit`    | `before_agent`                                               |
| `Stop`                | `after_agent`                                                |
| approval prompt       | `HumanInTheLoopMiddleware(interrupt_on={...})`               |

    Passed to create_agent(..., middleware=[...]).
    Order: before_* first to last, after_* last to first (reverse),
           wrap_* nest like function calls (first middleware wraps all others).

`HumanInTheLoopMiddleware` (verified):
- Runs in `after_model`: after the model answers, before any tool executes.
- Decisions: `approve`, `edit`, `reject` (set via `allowed_decisions`).
- **Requires a checkpointer**, because it pauses with `interrupt()`.
- `interrupt_on={"tool_name": False}` leaves a tool ungated.
- Default pauses once per model turn, `interrupt_mode="per_call"` once per tool call.

Prompt based rules are probabilistic. Middleware is deterministic.

### 1.4 Session Management and Workflow

    Stale context trap (same as original, provider independent):
        - re-fetch critical data before the action uses it
        - scratchpad files for intermediate state
        - TTL aware cache
        - checkpoints

| Need                         | LangGraph                                              |
| ---------------------------- | ------------------------------------------------------ |
| short term, one thread       | checkpointer (`InMemorySaver`, ...) + `thread_id`      |
| long term, across threads    | store (user preferences, facts)                        |
| shrink history               | `SummarizationMiddleware`                              |

Verified: a checkpointer keeps graph state snapshots per thread (conversation
continuity, human-in-the-loop, time travel, fault tolerance). A store keeps
application defined key-value data across threads.

    Choosing the workflow:
        prompt chaining -> fixed LangGraph graph (nodes and edges defined upfront)
        dynamic         -> create_agent, the model decides the next tool
        Plan -> chaining. Result -> adaptive.

## 2. Tool Design & MCP Integration

### 2.1 Tool Description Best Practices

    The description is the only instruction the model has about the tool.
    In LangChain it comes from the @tool docstring and the args schema.

    Perfect description:
        - clear purpose in one sentence
        - exact types, formats and rules for the inputs
        - examples
        - edge cases (empty or weird data)
        - when NOT to use the tool
        - return value, including the "not found" case

    EXAM tip: the most detailed, specific, exact answer is the good one.
    Vague tools ("search", "stuff") are bad.

### MCP (changed in langchain 1.4.0)

| Version                         | How                                                          |
| ------------------------------- | ------------------------------------------------------------ |
| `langchain < 1.4` (this project: 1.3.15) | `langchain-mcp-adapters`: `MultiServerMCPClient`, `await client.get_tools()` |
| `langchain >= 1.4.0` (beta)     | `pip install "langchain[mcp]"`, `from langchain.mcp import MCPAdapter`, `await adapter.list_tools()` |

- `MCPAdapter` is built on FastMCP, infers the transport from the target (URL, script via stdio, in-process server, `mcpServers` config dict) and raises a `LangChainBetaWarning`.
- It surfaces server elicitation as a LangGraph `interrupt()`, and exposes MCP annotations such as `destructive_hint` for gating destructive tools behind approval.
- This project's `src/mcp_server.py` is an example server (stdio).

## 2.2 Structured Error Responses

    Return errors as data the model can act on, not as stack traces.
    Handle them in wrap_tool_call middleware: catch the exception and return a
    ToolMessage with a clear, structured error (category, retryable or not, short message).
    ModelRetryMiddleware covers transient model call failures.

## 4. Prompt Engineering & Structured Output (mapping only)

    Anthropic:   tool use with a JSON schema, or structured outputs
    LangChain:   create_agent(..., response_format=...)

`response_format` accepts (verified):
- `ToolStrategy(schema)`: structured output through tool calling.
- `ProviderStrategy(schema)`: provider native structured output.
- a plain schema type (e.g. Pydantic model): LangChain picks `ProviderStrategy` if the model supports it (OpenAI, Anthropic, xAI), `ToolStrategy` otherwise.
- a raw JSON Schema dict must be wrapped in an explicit strategy.
- Result is in the `structured_response` key of the agent's final state.
- If tools are also given, the model must support tools and structured output together.

Deterministic exam rule: a schema enforced output beats parsing free text.

## 5. Context Management & Reliability (mapping only)

    Checkpointer         -> resumable, inspectable state per thread
    SummarizationMiddleware -> shrink history before the context window is exceeded
    ModelRetryMiddleware    -> retry transient model failures
    recursion_limit         -> bounded loop (GraphRecursionError)
    LangSmith               -> tracing (already a dependency in this project)

## What does NOT carry over

- Claude Code specific topics (domain 3: `CLAUDE.md`, slash commands, skills,
  `settings.json` hooks) have no LangChain equivalent.
- Raw `stop_reason` values such as `pause_turn` and `model_context_window_exceeded`
  are not normalized by LangChain.
- The exam tests the Anthropic API directly, so the raw loop
  (`while stop_reason == "tool_use"`) is still worth writing once by hand with
  the `anthropic` SDK.

## Sources

- Middleware overview and hooks: https://docs.langchain.com/oss/python/langchain/middleware/overview
- Human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Subagents: https://docs.langchain.com/oss/python/langchain/multi-agent/subagents
- Persistence and time travel: https://docs.langchain.com/oss/python/langgraph/persistence , https://docs.langchain.com/oss/python/langgraph/use-time-travel
- Recursion limit: https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit
- Structured output: https://docs.langchain.com/oss/python/langchain/structured-output
- MCP: https://docs.langchain.com/oss/python/langchain/mcp/index , https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters
