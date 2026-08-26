import base64
import re
from pathlib import Path
from typing import Any

import yaml

_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


def load_prompt_template(name: str) -> tuple[str, dict[str, Any]]:
    """Read ``resources/prompts/<name>.md`` and split off its model config block.

    The file has a fenced ```yaml block (e.g. ``model``, ``temperature``,
    ``max_tokens``) used to override the agent's ``ModelConfig``, rendered
    visibly in Markdown preview (unlike ``---`` frontmatter). Returns
    ``(system_prompt, overrides)``.
    """
    prompt_path = (
        Path(__file__).resolve().parent.parent / "resources" / "prompts" / f"{name}.md"
    )
    text = prompt_path.read_text(encoding="utf-8").strip()

    overrides: dict[str, Any] = {}
    match = _YAML_BLOCK_RE.search(text)
    if match:
        overrides = yaml.safe_load(match.group(1)) or {}
        text = text[match.end() :].strip()
    # Only the "## System prompt" section is the actual prompt; drop the
    # "why these settings" rationale text that precedes it.
    _, _, text = text.partition("## System prompt")
    return text.strip(), overrides


def encode_file_to_base64(file_path: str) -> str:
    """
    Encodes the contents of a file to a base64 string.

    Args:
        file_path (str): The path to the file to be encoded.

    Returns:
        str: The base64-encoded string of the file's contents.
    """
    with open(file_path, "rb") as file:
        file_contents = file.read()
        encoded_contents = base64.b64encode(file_contents).decode("utf-8")
    return encoded_contents
