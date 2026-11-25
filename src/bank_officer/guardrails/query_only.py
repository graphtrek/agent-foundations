"""After-model guardrail: enforce query-only behaviour."""

import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.messages import AIMessage
from langgraph.runtime import Runtime

from localization.messages import text

MUTATION_CLAIM_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bi('| )?ve (approved|applied|opened|updated|processed|transferred)",
        r"\bi have (approved|applied|opened|updated|processed|transferred)",
        r"\bjóváírtam\b",
        r"\bjóváhagytam\b",
        r"\bmódosítottam\b",
        r"\bmegnyitottam\b",
        r"\belindítottam az igénylést\b",
    )
]

class QueryOnlyEnforcementMiddleware(AgentMiddleware):
    """Rewrite any reply that claims to have performed a mutating action."""

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state["messages"]
        if not messages or not isinstance(messages[-1], AIMessage):
            return None
        text = str(messages[-1].content)
        if any(pattern.search(text) for pattern in MUTATION_CLAIM_PATTERNS):
            return {"messages": [AIMessage(content=text("query_only"))], "jump_to": "end"}
        return None
