# Claude Certified Architect Foundation Exam

## 0. The Exam Deconstructed

    - 60 multiple choice question
    - 120 minutes
    - 720/1000 passing score
    - 301 Professional level

| Domain | Topic                                  | Weight  | Questions |
| ------ | -------------------------------------- | ------- | --------- |
| 1.     | Agentic Architecture & Orchrestation   | 27%     | ~16       |
| 2.     | Tool Design & MCP Integration.         | 18%     | ~11       |
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
