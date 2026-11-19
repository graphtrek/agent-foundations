# Claude Certified Architect Foundation Exam

## 0. The Exam Deconstructed

    - 60 multiple choice question
    - 120 minutes
    - 720/1000 passing score
    - 301 Professional level

| Domain | Topic                                  | Weight  | Questions |
| ------ | -------------------------------------- | ------- | --------- |
| 1.     | Agentic Architecture & Orchrestation   | 27%     | ~16       |
| 2.     | Tool Design & MCP Integration          | 18%     | ~11       |
| 3.     | Claude Code Configuration & Workloads  | 20%     | ~12       |
| 4.     | Prompt Engineering & Structured Output | 20%     | ~12       |
| 5.     | Context Management & Reliability       | 15%     | ~9        |

### The exam consistently favour solutions that are deterministic and controled over anything probablilistic or fuzzy

### If unsure the choose the answare what are most controled

##  1. Agentic Architecture & Orcherstation

###   1.1 Agentic Loops and Core API

    Agentic Loop when Claude execute multi step tasks without human interventions at each step
    Plan -> Act -> Observe -> Decide -> Repeat
    During the loop AnthropicClient calls anthropic API
    Most important is controlling the loop.
    The loop is done when the stop reason comes back from the API response.
    The stop_reason can be:
        - end_turn
        - max_tokens
        - stop_sequence
        - tool_use
        - pause_turn
        - refusal
        - model_context_window_exceeded

    tool result appending before the next API call always the
    assistant message + new user message to the conversation history

[Anthropic SDK stop_reason](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons#end-turn)

### 1.2 Multi Agent Orhestation

    Hub and spoke pattern all communications have to go throught the hub
    sub-agents never talk to each others.
        - context isolations
        - focused tools
        - paralell execution
        - failure isolation
    task tool executes a new isolated agent only the orchestrator has
    after one response use multiple task tool executes sub-agents in paralell
    multiple responses sequencial
    dash resume: continue already existing session like commining to the main branch
    fork session: create a new session it gets the whole content then run independently
        does not modify the parent session it is like a new branch in GIT

[Anthropic SDK Build an orchestration mode](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-effort-example)

### 1.3 Hooks Programatic Enforcement

    Deterministic code run before and after the tool to enfore rules,
    validate parameters and/or block actions.
    Hooks are code that can run before tool (validate input) and/or after tool.
    Business rules, complience, security ... throws immediate errors.
    If a rule must be 100% enforced use a Hook.
    Prompt based respose always wrong.

[Anthropic SDK Citations](https://platform.claude.com/docs/en/build-with-claude/citations)

### 1.4 Session management and Workflow

    Session Operations:
        dash resume: continue already existing session like commiting to the main branch
        fork session: create a new session it gets the whole content then run independently
            does not modify the parent session it is like a new feature branch in GIT
    Stale Context trap:
        data retrived early in the session that make becaome outdated by the time it used
        - re-fetch critical data before the action use it
        - strachpad files to persist the intermediate state
        - TTL aware cache
        - checkpoints
    Coosing the workflow
        prompt chaining: use for predicatble linear fixed tasks. You define the workflow upfront
        dynamic adaptive: use for unpredictable results driven steps. The agent decides the next step.
        Is the next step determined by the plan or the Result?
        Plan -> chaining Result -> adaptive

[Antropic SDK Context Windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)

## 2. Tool Design & MCP Integration

### 2.1 Tool_Description_Best_Practices

    Why does a vague tool description cause your code to fail?
        The reason it is the descripion to the LLM how to use the tool.
    What is the perfect description?
        - Clear purpose in one simple sentence.
        - Exact types formats and rules for the input data.
        - Give it some examples.
        - Define egdge cases such as empty or weird data.
        - Tell when not use the tool.
        - Define the return value not just sucess but not found situations too.
    EXAM tip:
        The most detailed answer most specific exact is to good one
        Search, stuff ... are bad

## 2.2 Structured error responses

## Research

    - [Claude Certified Architect Exam Guide - Releases](https://github.com/daronyondem/claude-architect-exam-guide/releases)
    - [Claude Certified Architect Foundations - YouTube playlist](https://www.youtube.com/watch?v=VvKDoV39jAk&list=PLmiDJB5zE0KGwFtDCSqHfQG7SV6VeQ_31)
    - [Claude Certified Architect Foundations Certification Exam notes](https://github.com/OlivierAlter/Claude-Certified-Architect-Foundations-Certification-Exam/blob/main/Claude%20Certification%20Exam.md)

### Bank officer agent architecture (`bank-officer-agent-architecture-hu.html`) – used sources

Principles and chapters 1.1–1.4 of the page (agentic loop, `stop_reason`, hub-and-spoke, hooks, session management) come from the notes above. The sources below were used for the architecture, the proposals and the mapping to the LangChain/OpenAI implementation:

    - [Anthropic SDK stop_reason](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons#end-turn) – loop control, stop_reason table
    - [Anthropic SDK Build an orchestration mode](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-effort-example) – orchestrator / subagent pattern
    - [Antropic SDK Context Windows](https://platform.claude.com/docs/en/build-with-claude/context-windows) – stale context, `model_context_window_exceeded`
    - [Anthropic – Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) – start simple, prompt chaining vs. routing vs. adaptive agents ("Simplification, error handling and measurement" proposal)
    - [OpenAI – A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) – single-agent first, guardrails, model choice by measurement
    - [OpenAI Agents SDK – Guardrails](https://openai.github.io/openai-agents-python/guardrails/) – tripwire behaviour
    - [LangChain – Middleware overview and hooks](https://docs.langchain.com/oss/python/langchain/middleware/overview) – `before_model` / `after_model`, `PIIMiddleware` (hook equivalent)
    - [LangChain – Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) – subagent wrapped as a tool (Task/Agent tool equivalent)
    - [LangGraph – Recursion limit](https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit) – loop iteration limit
