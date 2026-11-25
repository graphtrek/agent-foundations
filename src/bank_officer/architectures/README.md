# architectures/

One folder per architecture: `<id>/architecture.yaml` (which parts the pipeline has) plus one
Markdown file per agent that architecture uses (`<id>/NN_<agent>.md`). The agent files are used
exactly as written - the YAML cannot override them - so to change an agent in one architecture,
edit that architecture's copy. `agents/agent_spec.py` builds every agent (model, tools, middleware,
system prompt) from these files. Same convention as `dev-vault/data/agents`.

File format:

```
# <Label>
<!-- model: openai/gpt-6-luna -->
<!-- temperature: 0.2 -->
<!-- tools: tool_a, tool_b -->
<!-- middleware: guardrails -->
<!--
Optional notes for humans (e.g. why these settings) - never sent to the model.
-->

<Body - becomes the agent's system prompt (## Role, ## Tools, ## Rules, ## Output).>
```

Filename is `<order-prefix>_<id>.md`. The prefix only orders the files; `<id>` (everything after
the first `_`) is the stable id the script looks the agent up by - renaming it breaks the lookup.

Directive lines (HTML comments, any order) right after the heading:

- `model`, `temperature`, `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `seed`
  - override the `TEXT_*` base model config (`config.text`).
- `tools` - comma-separated tool names the agent gets. This list is the source of truth: a listed
  tool the code does not provide is an error, a provided tool that is not listed is left out.
- `middleware` - the guardrail stack from `agent_spec.MIDDLEWARE_STACKS`: `guardrails`
  (default) or `coordinator`.
- `kind` - `agent` (default, a LangChain chat agent) or `decision` (a decision model such as
  TypeSafe Jev on OpenRouter's Decisions API, e.g. `00_endpoint_router.md`): the body becomes the
  decision question's instructions, `min_probability` sets the confidence below which the answer
  counts as "no decision", and `tools`, `middleware` and sampling settings do not apply.

Every HTML comment is stripped from the body before it is sent to the model.

`04_web_search/` (profile `web_search`, `mode: research`) has no router and no specialists: the
coordinator's tools are `web_search` and `research_links`, and `researcher:` names the subagent file
(`02_page_researcher.md`, tool `fetch_page`) that `research_links` runs once per link, in parallel.
