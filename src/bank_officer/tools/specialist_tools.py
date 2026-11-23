"""Coordinator tools that give the coordinator its specialists' data."""

from dataclasses import dataclass
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import StructuredTool
from pydantic import create_model

from agents.agent_spec import AgentFactory
from tools.branch_context import BranchContext, BranchState
from tools.specialist_runner import run_specialist, specialist_gate
from tools.tool_groups import CUSTOMER_FREE_GROUPS, GROUP_CATEGORIES, TOOL_GROUPS


@dataclass(frozen=True)
class SpecialistBinding:
    """One specialist the coordinator can delegate to: the wrapper tool is
    ``ask_<id>``, the specialist agent is built per call from ``factory`` with
    the ``group`` tools scoped to the selected customer."""

    id: str
    group: str
    description: str
    factory: AgentFactory



def make_specialist_tool(binding: SpecialistBinding) -> Any:
    """Wrapper tool that runs one specialist for the customer selected now."""

    def ask(question: str, runtime: ToolRuntime[BranchContext, BranchState]) -> str:
        customer_free = binding.group in CUSTOMER_FREE_GROUPS
        if not customer_free and (blocked := specialist_gate(runtime.state)) is not None:
            return blocked
        customer_id = "" if customer_free else runtime.state["current_customer_id"]
        agent = binding.factory.build(TOOL_GROUPS[binding.group](customer_id))
        matched = runtime.state.get("matched_endpoint")
        if matched is not None and matched.get("category") in GROUP_CATEGORIES[binding.group]:
            # Pass the router's pick on, so the specialist starts from the
            # endpoint that best fits the question instead of re-deriving it.
            question = (
                f"{question}\n\n(Endpoint-router hint: the best-matching endpoint is "
                f"{matched['method']} {matched['path']} - {matched['description']}. "
                "Prefer the tool that backs it.)"
            )
        return run_specialist(agent, question)

    return StructuredTool.from_function(
        func=ask,
        name=f"ask_{binding.id}",
        description=binding.description,
    )


def make_flat_tool(group: str, template: Any) -> Any:
    """A group tool the coordinator calls directly: same name, description and
    arguments as ``template``, but built per call for the customer selected
    now (the group tools close over one customer id)."""

    schema = create_model(
        f"{template.name}_args",
        __base__=template.args_schema,
        runtime=(ToolRuntime[BranchContext, BranchState], None),
    )

    def run(runtime: ToolRuntime[BranchContext, BranchState], **kwargs: Any) -> str:
        if (blocked := specialist_gate(runtime.state)) is not None:
            return blocked
        customer_id = runtime.state["current_customer_id"]
        scoped = {t.name: t for t in TOOL_GROUPS[group](customer_id)}[template.name]
        return scoped.invoke(kwargs)

    return StructuredTool.from_function(
        func=run,
        name=template.name,
        description=template.description,
        args_schema=schema,
    )
