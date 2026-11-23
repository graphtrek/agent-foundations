"""Run context and graph state of the branch coordinator."""

from dataclasses import dataclass
from typing import Any

from langchain.agents import AgentState


@dataclass
class BranchContext:
    officer_id: str
    branch_id: str


class BranchState(AgentState):
    current_customer_id: str | None
    matched_endpoint: dict[str, Any] | None
