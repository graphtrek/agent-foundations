"""Coordinator-only middleware: surface the router's result to the model."""

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain.messages import SystemMessage

from localization.language import LANGUAGE_NAMES, current_language


class MatchedEndpointContextMiddleware(AgentMiddleware):
    """Make ``state["matched_endpoint"]`` visible to the coordinator's model.

    The model only reads ``state["messages"]`` plus the static system prompt,
    so a custom state field set from outside is invisible to it. This appends
    a short factual note about it to the system message on every model call.
    """

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> Any:
        matched = request.state.get("matched_endpoint")
        if matched is None:
            note = "\n\nEndpoint-router result for this turn: no endpoint matched."
        else:
            note = (
                "\n\nEndpoint-router result for this turn: "
                f"category={matched['category']}, menu_path={matched['menu_path']}, "
                f"required_entitlement={matched['required_entitlement']}, "
                f"access_denied={matched.get('access_denied')}."
            )
        language = LANGUAGE_NAMES[current_language()]
        note += (
            f"\n\nReply language for this turn: {language}. Write your final answer in "
            f"{language}, even if tool results or product names are in another language."
        )
        base = request.system_message.content if request.system_message else ""
        request.system_message = SystemMessage(content=f"{base}{note}")
        return handler(request)
