import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def message_text(content: Any) -> str:
    """Return displayable text from a LangChain message content value."""
    if isinstance(content, list):
        return "\n".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        ).strip()
    return str(content).strip()


def message_was_truncated(message: Any) -> bool:
    """Return whether provider metadata says generation hit its token limit."""
    metadata = getattr(message, "response_metadata", {}) or {}
    finish_reason = metadata.get("finish_reason") or metadata.get("stop_reason")
    return finish_reason in {"length", "max_tokens"}


def _message_role(message: Any) -> str:
    message_type = str(getattr(message, "type", None) or message.__class__.__name__)
    return {"human": "User", "ai": "Assistant", "tool": "Tool"}.get(
        message_type, message_type.replace("_", " ").title()
    )


def _embed_local_images(
    content: str, output_dir: Path, image_paths: dict[str, Path]
) -> str:
    for image_path in image_paths.values():
        relative_path = Path(os.path.relpath(image_path, start=output_dir)).as_posix()
        image_uri = re.escape(image_path.as_uri())
        uri_pattern = re.compile(
            rf"(?m)^(?P<label>[^\n]*?)(?:`|\[)?{image_uri}"
            rf"(?:`|\])?(?:\({image_uri}\))?[ \t]*$"
        )

        def render_image(
            match: re.Match[str],
            image_path: Path = image_path,
            relative_path: str = relative_path,
        ) -> str:
            label = match.group("label").rstrip()
            alt_text = label.strip("*: ") or image_path.stem.replace("_", " ")
            return f"{label}\n\n![{alt_text}]({relative_path})"

        content = uri_pattern.sub(render_image, content)
    return content


def save_conversation(
    user_prompt: str,
    messages: list[Any],
    output_dir: Path,
    image_paths: dict[str, Path],
) -> Path:
    """Save a complete agent conversation as a timestamped Markdown file."""
    timestamp = datetime.now(UTC)
    sections = [
        "# Corporate Offsite Planner Conversation",
        "",
        f"**Timestamp:** {timestamp.isoformat(timespec='seconds')}",
        "",
        "## User Prompt",
        "",
        user_prompt,
        "",
        "## Conversation",
    ]

    for message in messages:
        if getattr(message, "additional_kwargs", {}).get("internal_recovery"):
            continue
        content = _embed_local_images(
            message_text(message.content), output_dir, image_paths
        )
        if content:
            role = _message_role(message)
            if role == "Assistant":
                sections.extend(
                    ["", "---", "", "## Assistant Recommendation", "", content]
                )
            else:
                sections.extend(["", f"### {role}", "", content])

    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"conversation-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.md"
    output_path = output_dir / file_name
    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return output_path
