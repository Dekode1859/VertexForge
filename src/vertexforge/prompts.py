"""Prompt provider abstractions for resolving Phoenix-managed prompts."""

from __future__ import annotations

import os
from typing import Protocol

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


class PromptRef(BaseModel):
    """Reference to a prompt managed outside the DSL, usually in Phoenix."""

    identifier: str | None = Field(
        default=None,
        description="Phoenix prompt name or ID. Required unless version_id is provided.",
    )
    tag: str | None = Field(
        default=None,
        description="Optional Phoenix prompt tag such as development, staging, or production.",
    )
    version_id: str | None = Field(
        default=None,
        description="Optional immutable Phoenix prompt version ID.",
    )

    @model_validator(mode="after")
    def validate_prompt_ref(self) -> "PromptRef":
        if not self.identifier and not self.version_id:
            raise ValueError("prompt_ref requires either identifier or version_id")
        if self.tag and not self.identifier:
            raise ValueError("prompt_ref tag requires identifier")
        return self


class PromptProvider(Protocol):
    """Runtime prompt resolver."""

    def get_system_prompt(self, prompt_ref: PromptRef) -> str:
        """Resolve a prompt reference to system prompt text."""


class StaticPromptProvider:
    """In-memory prompt provider for tests and local dry runs."""

    def __init__(self, prompts: dict[str, str]) -> None:
        self.prompts = prompts

    def get_system_prompt(self, prompt_ref: PromptRef) -> str:
        key = prompt_ref.version_id or prompt_ref.identifier
        if key is None or key not in self.prompts:
            raise ValueError(f"Prompt '{key}' was not found in the static prompt provider.")
        return self.prompts[key]


class PhoenixPromptProvider:
    """Resolve prompt text from Phoenix Prompt Hub."""

    def __init__(self, base_url: str | None = None) -> None:
        load_dotenv()
        self.base_url = (
            base_url
            or os.getenv("PHOENIX_CLIENT_BASE_URL")
            or os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
            or "http://localhost:6006"
        )
        self._client = None
        self._cache: dict[tuple[str | None, str | None, str | None], str] = {}

    @property
    def client(self):
        """Create the Phoenix client lazily so tests do not require the dependency."""
        if self._client is None:
            from phoenix.client import Client

            self._client = Client(base_url=self.base_url)
        return self._client

    def get_system_prompt(self, prompt_ref: PromptRef) -> str:
        """Fetch a Phoenix prompt and return system prompt text."""
        cache_key = (prompt_ref.identifier, prompt_ref.tag, prompt_ref.version_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if prompt_ref.version_id:
            prompt = self.client.prompts.get(prompt_version_id=prompt_ref.version_id)
        else:
            prompt = self.client.prompts.get(
                prompt_identifier=prompt_ref.identifier,
                tag=prompt_ref.tag,
            )

        prompt_text = _extract_system_prompt_text(prompt)
        self._cache[cache_key] = prompt_text
        return prompt_text


def _extract_system_prompt_text(prompt) -> str:
    """Extract system text from Phoenix prompt objects across SDK shapes."""
    try:
        formatted = prompt.format(variables={})
        messages = _get_messages(formatted)
        system_messages = [m for m in messages if _message_role(m) == "system"]
        if system_messages:
            return _message_content(system_messages[0])
        if messages:
            return _message_content(messages[0])
    except Exception:
        pass

    template = getattr(prompt, "template", None)
    messages = _get_messages(template) or _get_messages(getattr(prompt, "_template", None))
    if messages:
        for message in messages:
            if _message_role(message) == "system":
                return _message_content(message)
        return _message_content(messages[0])

    if isinstance(template, str):
        return template

    raise ValueError("Phoenix prompt did not contain extractable prompt text.")


def _get_messages(value) -> list:
    """Return prompt messages from Phoenix dict or object containers."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.get("messages") or [])
    return list(getattr(value, "messages", []) or [])


def _message_role(message) -> str | None:
    """Return a normalized chat message role."""
    role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
    return str(role).lower() if role is not None else None


def _message_content(message) -> str:
    """Return text content from Phoenix message representations."""
    content = message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                text_parts.append(str(part.get("text", "")))
            else:
                text_parts.append(str(getattr(part, "text", part)))
        return "".join(text_parts)
    return str(content)
