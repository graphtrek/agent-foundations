"""Architecture profiles: the agent architecture as data, not as wiring code.

An architecture lives in its own folder, ``src/bank_officer/architectures/<id>/``:
``architecture.yaml`` plus one ``NN_<agent>.md`` file per agent it uses. The
agent files are used exactly as written (model, sampling, tools, prompt); the
YAML never overrides them. The profile says which parts the
pipeline has - an endpoint router in front or not, one coordinator, and either
specialist sub-agents it delegates to (``mode: delegate``) or every data tool
directly (``mode: flat``, the single-agent baseline). The
``PipelineRegistry`` builds a profile's agents lazily and caches them, so the
terminal, the web chat and the eval runner can all try any architecture.

What is mandatory stays in code, not in the profile: the guardrail middleware
stack comes from each agent file's ``middleware`` directive, and the
entitlement checks live in the tools and the session, not in prompts.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langgraph.checkpoint.memory import InMemorySaver

from agent_spec import AgentSpec, load_agent_factories, load_agent_specs
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
PROFILE_FILE = "architecture.yaml"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MODES = ("delegate", "flat")
MAX_LABEL_CHARS = 100
MAX_DESCRIPTION_CHARS = 500
MAX_SPECIALISTS = 8


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
    synthesizer_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The profile as the plain mapping stored in the YAML file."""
        coordinator: dict[str, Any] = {
            "agent": self.coordinator_agent,
            "mode": self.mode,
            "specialists": [
                {"id": s.id, "tool_group": s.tool_group, "description": s.description}
                for s in self.specialists
            ],
        }
        if self.synthesizer_agent:
            coordinator["synthesizer"] = self.synthesizer_agent
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "router": {"enabled": self.router_enabled, "agent": self.router_agent},
            "coordinator": coordinator,
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


def parse_profile(raw: Any) -> ArchitectureProfile:
    """Validate the raw mapping of a profile (structure and value ranges)."""
    _require(isinstance(raw, dict), "a profile must be a mapping")
    unknown = set(raw) - {"id", "label", "description", "router", "coordinator"}
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
    synthesizer = coordinator.get("synthesizer")
    _require(
        synthesizer is None
        or (isinstance(synthesizer, str) and ID_RE.match(synthesizer) is not None),
        "coordinator.synthesizer must be an agent id",
    )
    _require(
        synthesizer is None or mode == "delegate",
        "only delegate mode can have a synthesizer",
    )
    if mode == "delegate":
        _require(bool(specialists), "delegate mode needs at least one specialist")
    else:
        _require(not specialists, "flat mode has no specialists")

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
        synthesizer_agent=synthesizer,
    )


def _agent_ids(profile: ArchitectureProfile) -> set[str]:
    ids = {profile.coordinator_agent} | {s.id for s in profile.specialists}
    if profile.router_enabled:
        ids.add(profile.router_agent)
    if profile.synthesizer_agent:
        ids.add(profile.synthesizer_agent)
    return ids


def folder_profile_id(folder_name: str) -> str:
    """The profile id of a folder: an optional ``NN_`` ordering prefix is not part
    of it (``03_router`` holds the profile ``router``)."""
    return re.sub(r"^\d+_", "", folder_name)


def profile_dir(profile_id: str) -> Path:
    """The folder of one architecture (its YAML and its agent files): ``<id>/`` or
    ``NN_<id>/``."""
    _require(
        isinstance(profile_id, str) and ID_RE.match(profile_id) is not None,
        "invalid profile id",
    )
    root = ARCHITECTURES_DIR.resolve()
    for folder in sorted(root.iterdir()) if root.is_dir() else []:
        if folder.is_dir() and folder_profile_id(folder.name) == profile_id:
            return folder
    return root / profile_id


def effective_specs(profile: ArchitectureProfile) -> dict[str, AgentSpec]:
    """The agents of the profile's own folder, as written, checked against the
    profile (ids, kinds) and the tools the code actually provides."""
    try:
        specs = load_agent_specs(profile_dir(profile.id))
    except ValueError as exc:
        raise ProfileError(str(exc)) from exc
    used = _agent_ids(profile)
    for agent_id in used:
        _require(
            agent_id in specs, f"{profile.id}/: no agent file for '{agent_id}'"
        )

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
        if profile.synthesizer_agent:
            allowed.add("ask_answer_synthesizer")
    _check_tools(coordinator, allowed)
    for specialist in profile.specialists:
        spec = specs[specialist.id]
        _require(spec.kind == "agent", f"specialist '{spec.id}' must be a chat agent")
        _check_tools(spec, set(group_tool_names(specialist.tool_group)))
    if profile.synthesizer_agent:
        synthesizer = specs[profile.synthesizer_agent]
        _require(synthesizer.kind == "agent", "the synthesizer must be a chat agent")
        _require(
            not synthesizer.tools,
            f"synthesizer '{synthesizer.id}' reads the specialists' answers itself and gets no tools",
        )
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
    return profile_dir(profile_id) / PROFILE_FILE


def load_profile(profile_id: str) -> ArchitectureProfile:
    path = _profile_path(profile_id)
    if not path.is_file():
        raise ProfileError(f"unknown architecture '{profile_id}'")
    profile = validate_profile(yaml.safe_load(path.read_text(encoding="utf-8")))
    _require(
        profile.id == profile_id,
        f"{profile_id}/{PROFILE_FILE}: id '{profile.id}' differs from the folder name",
    )
    return profile


def list_profiles() -> list[dict[str, str]]:
    """Id, label and description of every profile file; a broken file is listed
    with its error instead of hiding the others."""
    found: list[dict[str, str]] = []
    for path in sorted(ARCHITECTURES_DIR.glob(f"*/{PROFILE_FILE}")):
        try:
            profile = load_profile(folder_profile_id(path.parent.name))
            found.append(
                {"id": profile.id, "label": profile.label, "description": profile.description}
            )
        except (ProfileError, yaml.YAMLError, OSError) as exc:
            found.append({"id": folder_profile_id(path.parent.name), "label": path.parent.name, "description": "", "error": str(exc)})
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
            profile_dir(profile.id),
            self._base_config,
            self._api_key,
            only=_agent_ids(profile),
        )
        bindings = [
            SpecialistBinding(s.id, s.tool_group, s.description, factories[s.id])
            for s in profile.specialists
        ]
        synthesizer = (
            factories[profile.synthesizer_agent] if profile.synthesizer_agent else None
        )
        coordinator = factories[profile.coordinator_agent].build(
            create_branch_tools(bindings, flat=profile.mode == "flat", synthesizer=synthesizer),
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
