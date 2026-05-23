"""Model client implementations for real agent execution."""

from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI

from core.agents.runtime import AgentModelClient
from core.contracts.prompts import PromptMessage


class OpenAICompatibleChatModelClient(AgentModelClient):
    """OpenAI-compatible chat-completions client used by executable agents."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        response_format: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("An API key or local provider token is required for real agent execution.")
        self._model = model or os.getenv("OPENAI_CODEX_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5"
        self._response_format = response_format or {"type": "json_object"}
        self._client = AsyncOpenAI(
            api_key=resolved_api_key,
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
            timeout=timeout_seconds,
            default_headers=headers,
        )

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        """Execute the prompt through OpenAI and return message content."""

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            response_format=self._response_format,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned an empty message content.")
        return content

    async def stream_complete(self, messages: tuple[PromptMessage, ...]):
        """Stream chat-completion text deltas as they arrive from OpenAI."""

        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": message.role.value, "content": message.content}
                for message in messages
            ],
            response_format=self._response_format,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


OpenAIChatModelClient = OpenAICompatibleChatModelClient
