"""Build and cache the agents of an architecture profile."""

import threading
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from agents.agent_spec import load_agent_factories
from agents.profile import ArchitectureProfile
from agents.profile_loader import agent_ids, effective_specs, load_profile, profile_dir
from model_util import ModelConfigLike
from routing.decision_router import EndpointRouter
from tools.branch_context import BranchContext, BranchState
from tools.branch_tools import create_branch_tools
from tools.research_tool import create_research_tools
from tools.specialist_tools import SpecialistBinding


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
            only=agent_ids(profile),
        )
        bindings = [
            SpecialistBinding(s.id, s.tool_group, s.description, factories[s.id])
            for s in profile.specialists
        ]
        synthesizer = (
            factories[profile.synthesizer_agent] if profile.synthesizer_agent else None
        )
        if profile.mode == "research":
            assert profile.researcher_agent is not None  # guaranteed by parse_profile
            coordinator_tools = create_research_tools(
                factories[profile.researcher_agent], profile.max_links
            )
        else:
            coordinator_tools = create_branch_tools(
                bindings, flat=profile.mode == "flat", synthesizer=synthesizer
            )
        coordinator = factories[profile.coordinator_agent].build(
            coordinator_tools,
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
