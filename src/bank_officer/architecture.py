"""Architecture profiles: the agent architecture as data, not as wiring code.

A profile (``src/bank_officer/architectures/<id>.yaml``) says which parts the
pipeline has - an endpoint router in front or not, one coordinator, and either
specialist sub-agents it delegates to (``mode: delegate``) or every data tool
directly (``mode: flat``, the single-agent baseline) - and overrides the
``agents/*.md`` defaults per agent (model, sampling, tools, prompt). The
``PipelineRegistry`` builds a profile's agents lazily and caches them, so the
terminal, the web chat and the eval runner can all try any architecture.

What is mandatory stays in code, not in the profile: the guardrail middleware
stack cannot be overridden (see ``agent_spec.apply_overrides``), and the
entitlement checks live in the tools and the session, not in prompts.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from agent_spec import (
    OVERRIDE_KEYS,
    AgentSpec,
    apply_overrides,
    load_agent_factories,
    load_agent_specs,
)
from decision_router import EndpointRouter
from model_util import ModelConfigLike
from tools import (
    DIRECT_TOOL_NAMES,
    TOOL_GROUPS,
    BranchContext,
    BranchState,
    SpecialistBinding,
    create_branch_tools,
    group_tool_names,
)

ARCHITECTURES_DIR = Path(__file__).resolve().parent / "architectures"
AGENTS_EXAMPLE = "bank_officer"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MODES = ("delegate", "flat")
MAX_PROMPT_CHARS = 8000
MAX_APPEND_CHARS = 4000
MAX_LABEL_CHARS = 100
MAX_DESCRIPTION_CHARS = 500
MAX_SPECIALISTS = 8
_NUMBER_RANGES = {
    "temperature": (0.0, 2.0),
    "top_p": (0.0, 1.0),
    "frequency_penalty": (-2.0, 2.0),
    "presence_penalty": (-2.0, 2.0),
    "min_probability": (0.0, 1.0),
}


class ProfileError(ValueError):
    """The profile is malformed or refers to something that does not exist."""


@dataclass(frozen=True)
class SpecialistSpec:
    id: str
    tool_group: str
    description: str


@dataclass(frozen=True)
class ArchitectureProfile:
    id: str
    label: str
    description: str
    router_enabled: bool
    router_agent: str
    coordinator_agent: str
    mode: str
    specialists: tuple[SpecialistSpec, ...]
    agents: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """The profile as the plain mapping stored in the YAML file."""
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "router": {"enabled": self.router_enabled, "agent": self.router_agent},
            "coordinator": {
                "agent": self.coordinator_agent,
                "mode": self.mode,
                "specialists": [
                    {"id": s.id, "tool_group": s.tool_group, "description": s.description}
                    for s in self.specialists
                ],
            },
            "agents": self.agents,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def _text(value: Any, name: str, limit: int, *, required: bool = True) -> str:
    _require(isinstance(value, str), f"{name} must be text")
    value = value.strip()
    _require(not required or bool(value), f"{name} must not be empty")
    _require(len(value) <= limit, f"{name} is longer than {limit} characters")
    return value


def _check_override(agent_id: str, override: Any) -> dict[str, Any]:
    _require(isinstance(override, dict), f"agents.{agent_id} must be a mapping")
    unknown = set(override) - OVERRIDE_KEYS
    _require(not unknown, f"agents.{agent_id}: unknown keys {sorted(unknown)}")
    clean: dict[str, Any] = {}
    for key, value in override.items():
        where = f"agents.{agent_id}.{key}"
        if key == "model":
            clean[key] = _text(value, where, 100)
        elif key == "prompt":
            clean[key] = _text(value, where, MAX_PROMPT_CHARS)
        elif key == "prompt_append":
            clean[key] = _text(value, where, MAX_APPEND_CHARS, required=False)
        elif key == "tools":
            _require(
                isinstance(value, list) and all(isinstance(t, str) for t in value),
                f"{where} must be a list of tool names",
            )
            _require(len(value) <= 40, f"{where} has too many tools")
            clean[key] = [t.strip() for t in value]
        elif key in ("max_tokens", "seed"):
            _require(
                isinstance(value, int) and not isinstance(value, bool),
                f"{where} must be an integer",
            )
            if key == "max_tokens":
                _require(1 <= value <= 8000, f"{where} must be between 1 and 8000")
            clean[key] = value
        else:
            low, high = _NUMBER_RANGES[key]
            _require(
                isinstance(value, (int, float)) and not isinstance(value, bool),
                f"{where} must be a number",
            )
            _require(low <= value <= high, f"{where} must be between {low} and {high}")
            clean[key] = value
    return clean


def parse_profile(raw: Any) -> ArchitectureProfile:
    """Validate the raw mapping of a profile (structure and value ranges)."""
    _require(isinstance(raw, dict), "a profile must be a mapping")
    unknown = set(raw) - {"id", "label", "description", "router", "coordinator", "agents"}
    _require(not unknown, f"unknown top-level keys {sorted(unknown)}")
    profile_id = raw.get("id")
    _require(
        isinstance(profile_id, str) and ID_RE.match(profile_id) is not None,
        "id must match [a-z0-9][a-z0-9_-]{0,39}",
    )
    router = raw.get("router") or {}
    _require(isinstance(router, dict), "router must be a mapping")
    coordinator = raw.get("coordinator")
    _require(isinstance(coordinator, dict), "coordinator must be a mapping")
    mode = coordinator.get("mode", "delegate")
    _require(mode in MODES, f"coordinator.mode must be one of {MODES}")

    specialists: list[SpecialistSpec] = []
    raw_specialists = coordinator.get("specialists") or []
    _require(isinstance(raw_specialists, list), "coordinator.specialists must be a list")
    _require(len(raw_specialists) <= MAX_SPECIALISTS, "too many specialists")
    for item in raw_specialists:
        _require(isinstance(item, dict), "each specialist must be a mapping")
        spec_id = item.get("id")
        _require(
            isinstance(spec_id, str) and ID_RE.match(spec_id) is not None,
            "specialist id must match [a-z0-9][a-z0-9_-]{0,39}",
        )
        group = item.get("tool_group")
        _require(group in TOOL_GROUPS, f"specialist {spec_id}: unknown tool_group {group!r}")
        specialists.append(
            SpecialistSpec(
                spec_id,
                group,
                _text(item.get("description"), f"specialist {spec_id} description", 600),
            )
        )
    _require(
        len({s.id for s in specialists}) == len(specialists), "duplicate specialist ids"
    )
    if mode == "delegate":
        _require(bool(specialists), "delegate mode needs at least one specialist")
    else:
        _require(not specialists, "flat mode has no specialists")

    agents_raw = raw.get("agents") or {}
    _require(isinstance(agents_raw, dict), "agents must be a mapping")
    agents = {str(k): _check_override(str(k), v) for k, v in agents_raw.items()}

    return ArchitectureProfile(
        id=profile_id,
        label=_text(raw.get("label"), "label", MAX_LABEL_CHARS),
        description=_text(
            raw.get("description", ""), "description", MAX_DESCRIPTION_CHARS, required=False
        ),
        router_enabled=bool(router.get("enabled", False)),
        router_agent=str(router.get("agent", "endpoint_router")),
        coordinator_agent=str(coordinator.get("agent", "branch_coordinator")),
        mode=mode,
        specialists=tuple(specialists),
        agents=agents,
    )


def _agent_ids(profile: ArchitectureProfile) -> set[str]:
    ids = {profile.coordinator_agent} | {s.id for s in profile.specialists}
    if profile.router_enabled:
        ids.add(profile.router_agent)
    return ids


def agent_overrides(profile: ArchitectureProfile) -> dict[str, dict[str, Any]]:
    """The profile's per-agent overrides, plus - in delegate mode, unless the
    profile sets the coordinator's ``tools`` itself - the coordinator's tool
    list adjusted to the profile's specialists (an ``ask_<id>`` tool for each,
    none for specialists the file lists but the profile does not have)."""
    overrides = {agent_id: dict(o) for agent_id, o in profile.agents.items()}
    coordinator = overrides.get(profile.coordinator_agent, {})
    if profile.mode == "delegate" and "tools" not in coordinator:
        base = load_agent_specs(AGENTS_EXAMPLE).get(profile.coordinator_agent)
        _require(base is not None, f"unknown agent '{profile.coordinator_agent}'")
        wanted = [f"ask_{s.id}" for s in profile.specialists]
        tools = [t for t in base.tools if not t.startswith("ask_") or t in wanted]
        tools += [t for t in wanted if t not in tools]
        overrides[profile.coordinator_agent] = {**coordinator, "tools": tools}
    return overrides


def effective_specs(profile: ArchitectureProfile) -> dict[str, AgentSpec]:
    """The profile's agents with the overrides applied, checked against the
    agent files (ids, kinds) and the tools the code actually provides."""
    try:
        specs = load_agent_specs(AGENTS_EXAMPLE, agent_overrides(profile))
    except ValueError as exc:
        raise ProfileError(str(exc)) from exc
    used = _agent_ids(profile)
    stray = set(profile.agents) - used
    _require(not stray, f"overrides for agents not used by this profile: {sorted(stray)}")
    for agent_id in used:
        _require(agent_id in specs, f"unknown agent '{agent_id}'")

    if profile.router_enabled:
        _require(
            specs[profile.router_agent].kind == "decision",
            f"router agent '{profile.router_agent}' must be a 'kind: decision' file",
        )
    coordinator = specs[profile.coordinator_agent]
    _require(coordinator.kind == "agent", "the coordinator must be a chat agent")
    if profile.mode == "flat":
        allowed = set(DIRECT_TOOL_NAMES)
        for group in TOOL_GROUPS:
            allowed |= set(group_tool_names(group))
    else:
        allowed = set(DIRECT_TOOL_NAMES) | {f"ask_{s.id}" for s in profile.specialists}
    _check_tools(coordinator, allowed)
    for specialist in profile.specialists:
        spec = specs[specialist.id]
        _require(spec.kind == "agent", f"specialist '{spec.id}' must be a chat agent")
        _check_tools(spec, set(group_tool_names(specialist.tool_group)))
    return {agent_id: specs[agent_id] for agent_id in used}


def _check_tools(spec: AgentSpec, allowed: set[str]) -> None:
    unknown = [t for t in spec.tools if t not in allowed]
    _require(
        not unknown,
        f"agent '{spec.id}' lists tools it cannot have here: {unknown}",
    )
    _require(bool(spec.tools), f"agent '{spec.id}' has no tools")


def validate_profile(raw: Any) -> ArchitectureProfile:
    """Parse and fully validate a raw profile mapping (raises ``ProfileError``)."""
    profile = parse_profile(raw)
    effective_specs(profile)
    return profile


def _profile_path(profile_id: str) -> Path:
    _require(
        isinstance(profile_id, str) and ID_RE.match(profile_id) is not None,
        "invalid profile id",
    )
    path = (ARCHITECTURES_DIR / f"{profile_id}.yaml").resolve()
    _require(path.parent == ARCHITECTURES_DIR.resolve(), "invalid profile id")
    return path


def load_profile(profile_id: str) -> ArchitectureProfile:
    path = _profile_path(profile_id)
    if not path.is_file():
        raise ProfileError(f"unknown architecture '{profile_id}'")
    profile = validate_profile(yaml.safe_load(path.read_text(encoding="utf-8")))
    _require(profile.id == profile_id, f"{path.name}: id '{profile.id}' differs from the file name")
    return profile


def list_profiles() -> list[dict[str, str]]:
    """Id, label and description of every profile file; a broken file is listed
    with its error instead of hiding the others."""
    found: list[dict[str, str]] = []
    for path in sorted(ARCHITECTURES_DIR.glob("*.yaml")):
        try:
            profile = load_profile(path.stem)
            found.append(
                {"id": profile.id, "label": profile.label, "description": profile.description}
            )
        except (ProfileError, yaml.YAMLError, OSError) as exc:
            found.append({"id": path.stem, "label": path.stem, "description": "", "error": str(exc)})
    return found


@dataclass(frozen=True)
class Pipeline:
    """The built agents of one profile; shared by every chat that uses it."""

    profile: ArchitectureProfile
    router: EndpointRouter | None
    coordinator: Any


class PipelineRegistry:
    """Builds and caches one ``Pipeline`` per profile. Each pipeline has its
    own coordinator checkpointer, so chats are told apart by thread id."""

    def __init__(self, base_config: ModelConfigLike, api_key: str) -> None:
        self._base_config = base_config
        self._api_key = api_key
        self._cache: dict[str, Pipeline] = {}
        self._lock = threading.Lock()

    def invalidate(self, profile_id: str | None = None) -> None:
        with self._lock:
            if profile_id is None:
                self._cache.clear()
            else:
                self._cache.pop(profile_id, None)

    def get(self, profile_id: str) -> Pipeline:
        with self._lock:
            pipeline = self._cache.get(profile_id)
            if pipeline is None:
                pipeline = self._build(load_profile(profile_id))
                self._cache[profile_id] = pipeline
            return pipeline

    def _build(self, profile: ArchitectureProfile) -> Pipeline:
        specs = effective_specs(profile)
        factories = load_agent_factories(
            AGENTS_EXAMPLE,
            self._base_config,
            self._api_key,
            overrides=agent_overrides(profile),
            only=_agent_ids(profile),
        )
        bindings = [
            SpecialistBinding(s.id, s.tool_group, s.description, factories[s.id])
            for s in profile.specialists
        ]
        coordinator = factories[profile.coordinator_agent].build(
            create_branch_tools(bindings, flat=profile.mode == "flat"),
            state_schema=BranchState,
            context_schema=BranchContext,
            checkpointer=InMemorySaver(),
        )
        # The router is a decision model (kind: decision), not a chat agent,
        # and stateless across turns: it sees only the current question.
        router = (
            EndpointRouter(specs[profile.router_agent], self._api_key)
            if profile.router_enabled
            else None
        )
        return Pipeline(profile, router, coordinator)
