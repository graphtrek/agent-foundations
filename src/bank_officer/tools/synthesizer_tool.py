"""The answer-synthesizer wrapper tool: merges several specialists' answers."""

from collections.abc import Sequence
from typing import Any

from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime
from langchain_core.tools import StructuredTool

from agents.agent_spec import AgentFactory
from session.conversation_util import message_text
from tools.branch_context import BranchContext, BranchState
from tools.specialist_runner import run_specialist

SYNTHESIZER_TOOL = "ask_answer_synthesizer"


def current_turn_specialist_answers(messages: Sequence[Any]) -> list[tuple[str, str]]:
    """``(specialist tool name, answer)`` of every specialist that answered
    in the current turn (after the last officer message), in call order."""
    last_human = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1
    )
    return [
        (m.name, message_text(m.content))
        for m in messages[last_human + 1 :]
        if isinstance(m, ToolMessage)
        and (m.name or "").startswith("ask_")
        and m.name != SYNTHESIZER_TOOL
    ]


def make_synthesizer_tool(factory: AgentFactory) -> Any:
    """Wrapper tool for the answer-synthesizer subagent. The specialists'
    answers are read from the turn's own tool results in code, not retyped by
    the coordinator, so nothing is lost or reworded on the way. With fewer
    than two answers there is nothing to reconcile and the answer is passed on
    unchanged."""

    def ask(question: str, runtime: ToolRuntime[BranchContext, BranchState]) -> str:
        answers = current_turn_specialist_answers(runtime.state["messages"])
        if len(answers) < 2:
            only = answers[0][1] if answers else ""
            return f"Only one specialist answered; relay this answer as is:\n{only}"
        if any(text.startswith("ACCESS DENIED") for _, text in answers):
            # A refusal is final text from code; it is never merged or rephrased.
            return next(t for _, t in answers if t.startswith("ACCESS DENIED"))
        briefing = "\n\n".join(f"### {name}\n{text}" for name, text in answers)
        agent = factory.build([])
        return run_specialist(
            agent, f"Officer question: {question}\n\nSpecialist answers:\n{briefing}"
        )

    return StructuredTool.from_function(
        func=ask,
        name=SYNTHESIZER_TOOL,
        description=(
            "Merge the answers of two or more specialists into one consistent answer. "
            "Call it, with the officer's question only, after more than one specialist "
            "answered in this turn; it reads their answers itself."
        ),
    )
