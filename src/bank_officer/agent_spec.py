"""Build agents from one Markdown definition file per agent.

Each agent of an example lives in its own ``NN_<id>.md`` file in a
directory (e.g. ``src/bank_officer/agents/``), following the same
persona-file convention as ``dev-vault/data/agents``:

    # <Label>
    <!-- model: openai/gpt-6-luna -->
    <!-- temperature: 0.2 -->
    <!-- tools: list_accounts, get_transaction_history -->
    <!-- middleware: guardrails -->
    <!--
    Free-form notes for humans (e.g. why these settings); never sent to the model.
    -->

    ## Role
    ...the rest of the body is the agent's system prompt...

- The numeric prefix only orders the files; ``<id>`` (everything after the
  first ``_``) is the stable id the runnable script looks the agent up by.
- Directive lines (``<!-- key: value -->``) come right after the heading.
  Model directives (``model``, ``temperature``, ``max_tokens``, ``top_p``,
  ``frequency_penalty``, ``presence_penalty``, ``seed``) override the base
  model config. ``tools`` lists the tool names the agent gets: it is the
  single source of truth, so a listed tool the code doesn't provide is an
  error and a provided tool that isn't listed is left out. ``middleware``
  names a stack from ``MIDDLEWARE_STACKS``. ``kind: decision`` marks a
  decision model (OpenRouter Decisions API) instead of a chat agent: its body
  becomes the decision question's instructions, ``min_probability`` is the
  confidence below which its answer counts as "no decision", and ``tools`` /
  ``middleware`` do not apply.
- Every HTML comment is stripped from the body before it becomes the
  system prompt.
"""

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, cast

import yaml
from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel

from guardrails import (
    build_coordinator_middleware,
    build_guardrail_middleware,
)
from model_util import ModelConfigLike, get_openrouter_model

AGENTS_DIR = Path(__file__).resolve().parent / "agents"

MIDDLEWARE_STACKS: dict[str, Callable[[], list[Any]]] = {
    "guardrails": build_guardrail_middleware,
    "coordinator": build_coordinator_middleware,
}

_DIRECTIVE_RE = re.compile(r"^<!--\s*([a-z_]+)\s*:\s*(.*?)\s*-->$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_MODEL_KEYS = {
    "model": "name",
    "temperature": "temperature",
    "max_tokens": "max_tokens",
    "top_p": "top_p",
    "frequency_penalty": "frequency_penalty",
    "presence_penalty": "presence_penalty",
    "seed": "seed",
}
_KNOWN_KEYS = set(_MODEL_KEYS) | {"kind", "tools", "middleware", "min_probability"}
AGENT_KINDS = {"agent", "decision"}


@dataclass(frozen=True)
class AgentSpec:
    id: str
    label: str
    system_prompt: str
    model_overrides: dict[str, Any]
    tools: tuple[str, ...]
    middleware: str
    kind: str = "agent"
    min_probability: float = 0.0


def parse_agent_file(path: Path) -> AgentSpec:
    """Parse one ``NN_<id>.md`` agent definition."""
    _, sep, agent_id = path.stem.partition("_")
    if not sep or not agent_id:
        raise ValueError(f"{path.name}: file name must be '<order>_<id>.md'")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"{path.name}: first line must be a '# <Label>' heading")
    label = lines[0][2:].strip()

    directives: dict[str, str] = {}
    body_start = 1
    for index, line in enumerate(lines[1:], start=1):
        match = _DIRECTIVE_RE.match(line.strip())
        if not match:
            body_start = index
            break
        key, value = match.groups()
        if key not in _KNOWN_KEYS:
            raise ValueError(f"{path.name}: unknown directive '{key}'")
        directives[key] = value
    else:
        body_start = len(lines)

    kind = directives.get("kind", "agent")
    if kind not in AGENT_KINDS:
        raise ValueError(f"{path.name}: unknown kind '{kind}'")
    middleware = directives.get("middleware", "guardrails")
    if middleware not in MIDDLEWARE_STACKS:
        raise ValueError(f"{path.name}: unknown middleware stack '{middleware}'")
    overrides = {
        field: yaml.safe_load(directives[key])
        for key, field in _MODEL_KEYS.items()
        if key in directives
    }
    tools = tuple(t.strip() for t in directives.get("tools", "").split(",") if t.strip())
    body = _COMMENT_RE.sub("", "\n".join(lines[body_start:])).strip()
    if not body:
        raise ValueError(f"{path.name}: empty system prompt")
    min_probability = float(directives.get("min_probability", 0.0))
    return AgentSpec(
        agent_id, label, body, overrides, tools, middleware, kind, min_probability
    )


OVERRIDE_KEYS = set(_MODEL_KEYS) | {"tools", "prompt", "prompt_append", "min_probability"}


def apply_overrides(spec: AgentSpec, override: dict[str, Any]) -> AgentSpec:
    """Return ``spec`` with an architecture profile's per-agent overrides applied.

    Same keys as the file directives (``model``, ``temperature``, ... ``tools``,
    ``min_probability``) plus ``prompt`` (replaces the system prompt) and
    ``prompt_append`` (added after it). The middleware stack is deliberately not
    overridable, so a profile can never switch the guardrails off."""
    unknown = set(override) - OVERRIDE_KEYS
    if unknown:
        raise ValueError(f"agent '{spec.id}': unknown override keys {sorted(unknown)}")
    model_overrides = dict(spec.model_overrides)
    for key, field in _MODEL_KEYS.items():
        if key in override:
            model_overrides[field] = override[key]
    prompt = str(override["prompt"]).strip() if "prompt" in override else spec.system_prompt
    if override.get("prompt_append"):
        prompt = f"{prompt}\n\n{str(override['prompt_append']).strip()}"
    if not prompt:
        raise ValueError(f"agent '{spec.id}': empty system prompt")
    tools = tuple(override["tools"]) if "tools" in override else spec.tools
    return replace(
        spec,
        system_prompt=prompt,
        model_overrides=model_overrides,
        tools=tools,
        min_probability=float(override.get("min_probability", spec.min_probability)),
    )


def load_agent_specs(
    example: str, overrides: dict[str, dict[str, Any]] | None = None
) -> dict[str, AgentSpec]:
    """Load every ``*.md`` agent file (except README.md) of one example, by id,
    with an optional architecture profile's per-agent ``overrides`` applied."""
    directory = AGENTS_DIR
    specs: dict[str, AgentSpec] = {}
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        spec = parse_agent_file(path)
        if spec.id in specs:
            raise ValueError(f"{path.name}: duplicate agent id '{spec.id}'")
        specs[spec.id] = spec
    for agent_id, override in (overrides or {}).items():
        if agent_id not in specs:
            raise ValueError(f"override for unknown agent '{agent_id}'")
        specs[agent_id] = apply_overrides(specs[agent_id], override)
    return specs


@dataclass(frozen=True)
class AgentFactory:
    """An agent spec with its chat model built once, ready to assemble agents
    from - repeatedly, for agents rebuilt per call with freshly scoped tools."""

    spec: AgentSpec
    model: BaseChatModel

    def build(self, tools: list[Any], **create_agent_kwargs: Any) -> Any:
        provided = {t.name: t for t in tools}
        missing = [name for name in self.spec.tools if name not in provided]
        if missing:
            raise ValueError(f"agent '{self.spec.id}' lists unknown tools: {missing}")
        return create_agent(
            model=self.model,
            tools=[provided[name] for name in self.spec.tools],
            system_prompt=self.spec.system_prompt,
            middleware=MIDDLEWARE_STACKS[self.spec.middleware](),
            name=self.spec.id,
            **create_agent_kwargs,
        )


def load_agent_factories(
    example: str,
    base_config: ModelConfigLike,
    api_key: str,
    overrides: dict[str, dict[str, Any]] | None = None,
    only: set[str] | None = None,
) -> dict[str, AgentFactory]:
    """Load an example's ``kind: agent`` files and build each one's chat model
    once. ``kind: decision`` files (decision models such as TypeSafe Jev, not
    callable as chat models) are built by their own client instead, e.g.
    ``decision_router.EndpointRouter``. ``overrides`` are an architecture
    profile's per-agent changes; ``only`` limits which agents get a model."""
    factories: dict[str, AgentFactory] = {}
    for agent_id, spec in load_agent_specs(example, overrides).items():
        if spec.kind != "agent" or (only is not None and agent_id not in only):
            continue
        config = cast(ModelConfigLike, replace(cast(Any, base_config), **spec.model_overrides))
        factories[agent_id] = AgentFactory(
            spec, get_openrouter_model(config, api_key, reasoning={"effort": "low"})
        )
    return factories
