import getpass
import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass
class ModelConfig:
    """Configuration for an OpenRouter chat model."""

    name: str
    # Randomness of sampling: higher = more creative, lower = more focused/deterministic.
    temperature: float = 0.7
    # Hard cap on the number of tokens generated in the response.
    max_tokens: int = 500
    # Nucleus sampling: keep only the smallest set of tokens whose probs sum to top_p.
    top_p: float | None = None
    # Penalize tokens by how often they already appeared (reduces verbatim repetition).
    frequency_penalty: float | None = None
    # Penalize tokens that appeared at all (pushes the model toward new topics).
    presence_penalty: float | None = None
    # Fix the RNG for reproducible outputs given the same input (best-effort).
    seed: int | None = None


@dataclass
class AppConfig:
    """Application configuration loaded from the environment."""

    openrouter_api_key: str
    planner: ModelConfig
    vision: ModelConfig
    text: ModelConfig


def _opt_float(name: str) -> float | None:
    """Read an optional float env var, returning None when it is unset/empty."""
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else None


def _opt_int(name: str) -> int | None:
    """Read an optional int env var, returning None when it is unset/empty."""
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else None


def _model_config(
    prefix: str,
    default_name: str,
    default_temperature: float,
    default_max_tokens: int,
) -> ModelConfig:
    """Build a ModelConfig from ``<PREFIX>_*`` env vars (see .env.example)."""
    return ModelConfig(
        name=os.environ.get(f"{prefix}_MODEL", default_name),
        temperature=float(os.environ.get(f"{prefix}_TEMPERATURE", default_temperature)),
        max_tokens=int(os.environ.get(f"{prefix}_MAX_TOKENS", default_max_tokens)),
        top_p=_opt_float(f"{prefix}_TOP_P"),
        frequency_penalty=_opt_float(f"{prefix}_FREQUENCY_PENALTY"),
        presence_penalty=_opt_float(f"{prefix}_PRESENCE_PENALTY"),
        seed=_opt_int(f"{prefix}_SEED"),
    )


def load_config() -> AppConfig:
    env_path = find_dotenv()
    print("\nLoading configuration...")
    if env_path:
        print(f"Loading environment variables from: {env_path}")
        load_dotenv(env_path)
    else:
        print(
            "No .env file found. Please ensure that the .env file exists "
            "in the project directory."
        )

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key is None:
        print("Please enter your OpenRouter API key:")
        api_key = getpass.getpass("API Key: ")
        os.environ["OPENROUTER_API_KEY"] = api_key

    if api_key and api_key.strip():
        print("OPENROUTER_API_KEY environment variable is set.")
    else:
        print("OPENROUTER_API_KEY environment variable is not set.")

    if os.environ.get("LANGCHAIN_DEBUG") == "true":
        print("LANGCHAIN_DEBUG is set to true. Debugging information will be printed.")

    return AppConfig(
        openrouter_api_key=api_key,
        planner=_model_config("PLANNER", "openai/gpt-oss-120b", 0.7, 900),
        vision=_model_config("VISION", "google/gemma-4-26b-a4b-it", 0.3, 500),
        text=_model_config("TEXT", "poolside/laguna-s-2.1", 0.7, 500),
    )
