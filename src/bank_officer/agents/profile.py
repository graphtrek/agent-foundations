"""Architecture profile: the pipeline's shape as data (parsed from ``architecture.yaml``).

The profile says which parts the pipeline has - an endpoint router in front or
not, one coordinator, and either specialist sub-agents it delegates to
(``mode: delegate``) or every data tool directly (``mode: flat``, the
single-agent baseline). The agent files are used exactly as written; the YAML
never overrides them.
"""

import re
from dataclasses import dataclass
from typing import Any

from tools.tool_groups import TOOL_GROUPS

PROFILE_FILE = "architecture.yaml"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
MODES = ("delegate", "flat", "research")
MAX_RESEARCH_LINKS = 5
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
    researcher_agent: str | None = None  # research mode: the page-researcher subagent
    max_links: int = 3  # research mode: links read in parallel per question
    label_en: str = ""  # English label / description, shown when the UI language is English
    description_en: str = ""

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
        if self.researcher_agent:
            coordinator["researcher"] = self.researcher_agent
            coordinator["max_links"] = self.max_links
        profile: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "router": {"enabled": self.router_enabled, "agent": self.router_agent},
            "coordinator": coordinator,
        }
        if self.label_en:
            profile["label_en"] = self.label_en
        if self.description_en:
            profile["description_en"] = self.description_en
        return profile


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def _text(value: Any, name: str, limit: int, *, required: bool = True) -> str:
    require(isinstance(value, str), f"{name} must be text")
    value = value.strip()
    require(not required or bool(value), f"{name} must not be empty")
    require(len(value) <= limit, f"{name} is longer than {limit} characters")
    return value


def parse_profile(raw: Any) -> ArchitectureProfile:
    """Validate the raw mapping of a profile (structure and value ranges)."""
    require(isinstance(raw, dict), "a profile must be a mapping")
    unknown = set(raw) - {"id", "label", "description", "label_en", "description_en", "router", "coordinator"}
    require(not unknown, f"unknown top-level keys {sorted(unknown)}")
    profile_id = raw.get("id")
    require(
        isinstance(profile_id, str) and ID_RE.match(profile_id) is not None,
        "id must match [a-z0-9][a-z0-9_-]{0,39}",
    )
    router = raw.get("router") or {}
    require(isinstance(router, dict), "router must be a mapping")
    coordinator = raw.get("coordinator")
    require(isinstance(coordinator, dict), "coordinator must be a mapping")
    mode = coordinator.get("mode", "delegate")
    require(mode in MODES, f"coordinator.mode must be one of {MODES}")

    specialists: list[SpecialistSpec] = []
    raw_specialists = coordinator.get("specialists") or []
    require(isinstance(raw_specialists, list), "coordinator.specialists must be a list")
    require(len(raw_specialists) <= MAX_SPECIALISTS, "too many specialists")
    for item in raw_specialists:
        require(isinstance(item, dict), "each specialist must be a mapping")
        spec_id = item.get("id")
        require(
            isinstance(spec_id, str) and ID_RE.match(spec_id) is not None,
            "specialist id must match [a-z0-9][a-z0-9_-]{0,39}",
        )
        group = item.get("tool_group")
        require(group in TOOL_GROUPS, f"specialist {spec_id}: unknown tool_group {group!r}")
        specialists.append(
            SpecialistSpec(
                spec_id,
                group,
                _text(item.get("description"), f"specialist {spec_id} description", 600),
            )
        )
    require(
        len({s.id for s in specialists}) == len(specialists), "duplicate specialist ids"
    )
    synthesizer = coordinator.get("synthesizer")
    require(
        synthesizer is None
        or (isinstance(synthesizer, str) and ID_RE.match(synthesizer) is not None),
        "coordinator.synthesizer must be an agent id",
    )
    require(
        synthesizer is None or mode == "delegate",
        "only delegate mode can have a synthesizer",
    )
    researcher = coordinator.get("researcher")
    require(
        researcher is None
        or (isinstance(researcher, str) and ID_RE.match(researcher) is not None),
        "coordinator.researcher must be an agent id",
    )
    max_links = coordinator.get("max_links", 3)
    require(
        isinstance(max_links, int)
        and not isinstance(max_links, bool)
        and 1 <= max_links <= MAX_RESEARCH_LINKS,
        f"coordinator.max_links must be 1..{MAX_RESEARCH_LINKS}",
    )
    if mode == "delegate":
        require(bool(specialists), "delegate mode needs at least one specialist")
        require(researcher is None, "only research mode has a researcher")
    elif mode == "research":
        require(researcher is not None, "research mode needs a coordinator.researcher")
        require(not specialists and synthesizer is None, "research mode has no specialists or synthesizer")
    else:
        require(not specialists, "flat mode has no specialists")
        require(researcher is None, "only research mode has a researcher")

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
        researcher_agent=researcher,
        max_links=max_links,
        label_en=_text(raw.get("label_en", ""), "label_en", MAX_LABEL_CHARS, required=False),
        description_en=_text(
            raw.get("description_en", ""), "description_en", MAX_DESCRIPTION_CHARS, required=False
        ),
    )
