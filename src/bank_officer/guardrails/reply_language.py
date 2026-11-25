"""Middleware that tells a model which language to reply in."""

from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain.messages import SystemMessage

from localization.language import LANGUAGE_NAMES, current_language


class ReplyLanguageMiddleware(AgentMiddleware):
    """Append the turn's reply language to the system message on every model call."""

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> Any:
        language = LANGUAGE_NAMES[current_language()]
        note = (
            f"\n\nReply language for this turn: {language}. Write your final answer in "
            f"{language}, even if search results or pages are in another language."
        )
        base = request.system_message.content if request.system_message else ""
        request.system_message = SystemMessage(content=f"{base}{note}")
        return handler(request)
