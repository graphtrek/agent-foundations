"""Load and validate architecture profiles from ``architectures/<id>/``.

An architecture lives in its own folder: ``architecture.yaml`` plus one
``NN_<agent>.md`` file per agent it uses. What is mandatory stays in code, not
in the profile: the guardrail stack comes from each agent file's
``middleware`` directive, and the entitlement checks live in the tools and the
session, not in prompts.
"""

import re
from pathlib import Path
from typing import Any

import yaml

from agents.agent_spec import AgentSpec, load_agent_specs
from agents.profile import (
    ID_RE,
    PROFILE_FILE,
    ArchitectureProfile,
    ProfileError,
    parse_profile,
    require,
)
from tools.synthesizer_tool import SYNTHESIZER_TOOL
from tools.tool_groups import DIRECT_TOOL_NAMES, TOOL_GROUPS, group_tool_names

ARCHITECTURES_DIR = Path(__file__).resolve().parent.parent / "architectures"

def agent_ids(profile: ArchitectureProfile) -> set[str]:
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
    require(
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
    used = agent_ids(profile)
    for agent_id in used:
        require(
            agent_id in specs, f"{profile.id}/: no agent file for '{agent_id}'"
        )

    if profile.router_enabled:
        require(
            specs[profile.router_agent].kind == "decision",
            f"router agent '{profile.router_agent}' must be a 'kind: decision' file",
        )
    coordinator = specs[profile.coordinator_agent]
    require(coordinator.kind == "agent", "the coordinator must be a chat agent")
    if profile.mode == "flat":
        allowed = set(DIRECT_TOOL_NAMES)
        for group in TOOL_GROUPS:
            allowed |= set(group_tool_names(group))
    else:
        allowed = set(DIRECT_TOOL_NAMES) | {f"ask_{s.id}" for s in profile.specialists}
        if profile.synthesizer_agent:
            allowed.add(SYNTHESIZER_TOOL)
    _check_tools(coordinator, allowed)
    for specialist in profile.specialists:
        spec = specs[specialist.id]
        require(spec.kind == "agent", f"specialist '{spec.id}' must be a chat agent")
        _check_tools(spec, set(group_tool_names(specialist.tool_group)))
    if profile.synthesizer_agent:
        synthesizer = specs[profile.synthesizer_agent]
        require(synthesizer.kind == "agent", "the synthesizer must be a chat agent")
        require(
            not synthesizer.tools,
            f"synthesizer '{synthesizer.id}' reads the specialists' answers itself and gets no tools",
        )
    return {agent_id: specs[agent_id] for agent_id in used}


def _check_tools(spec: AgentSpec, allowed: set[str]) -> None:
    unknown = [t for t in spec.tools if t not in allowed]
    require(
        not unknown,
        f"agent '{spec.id}' lists tools it cannot have here: {unknown}",
    )
    require(bool(spec.tools), f"agent '{spec.id}' has no tools")


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
    require(
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
                {
                    "id": profile.id,
                    "label": profile.label,
                    "description": profile.description,
                    "label_en": profile.label_en,
                    "description_en": profile.description_en,
                }
            )
        except (ProfileError, yaml.YAMLError, OSError) as exc:
            found.append({"id": folder_profile_id(path.parent.name), "label": path.parent.name, "description": "", "error": str(exc)})
    return found
