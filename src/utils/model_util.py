import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Protocol, cast

import yaml
from langchain.chat_models import BaseChatModel, init_chat_model

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


class ModelConfigLike(Protocol):
    name: str
    temperature: float
    max_tokens: int
    top_p: float | None
    frequency_penalty: float | None
    presence_penalty: float | None
    seed: int | None


def load_prompt_template(name: str) -> tuple[str, dict[str, Any]]:
    """Read a prompt template and return its system prompt and model overrides."""
    prompt_path = (
        Path(__file__).resolve().parent.parent / "resources" / "prompts" / f"{name}.md"
    )
    text = prompt_path.read_text(encoding="utf-8").strip()

    overrides: dict[str, Any] = {}
    match = _YAML_BLOCK_RE.search(text)
    if match:
        overrides = yaml.safe_load(match.group(1)) or {}
        text = text[match.end() :].strip()
    _, _, text = text.partition("## System prompt")
    return text.strip(), overrides


def get_openrouter_model(config: ModelConfigLike, api_key: str) -> BaseChatModel:
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
    return init_chat_model(**params)


def load_configured_model(
    prompt_name: str, base_config: ModelConfigLike, api_key: str
) -> tuple[str, BaseChatModel]:
    """Load a prompt and model, applying the prompt's configuration overrides."""
    system_prompt, overrides = load_prompt_template(prompt_name)
    model_config = cast(ModelConfigLike, replace(cast(Any, base_config), **overrides))
    return system_prompt, get_openrouter_model(model_config, api_key)
