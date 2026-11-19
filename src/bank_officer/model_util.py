from typing import Any, Protocol

from langchain.chat_models import BaseChatModel, init_chat_model


class ModelConfigLike(Protocol):
    name: str
    temperature: float
    max_tokens: int
    top_p: float | None
    frequency_penalty: float | None
    presence_penalty: float | None
    seed: int | None


def get_openrouter_model(
    config: ModelConfigLike, api_key: str, reasoning: dict[str, Any] | None = None
) -> BaseChatModel:
    """Create an OpenRouter chat model from a model configuration."""
    params: dict[str, Any] = {
        "model": config.name,
        "model_provider": "openrouter",
        "api_key": api_key,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if config.top_p is not None:
        params["top_p"] = config.top_p
    if config.frequency_penalty is not None:
        params["frequency_penalty"] = config.frequency_penalty
    if config.presence_penalty is not None:
        params["presence_penalty"] = config.presence_penalty
    if config.seed is not None:
        params["seed"] = config.seed
    if reasoning is not None:
        params["reasoning"] = reasoning
    return init_chat_model(**params)
