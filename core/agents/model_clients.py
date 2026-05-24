"""Model client implementations for real agent execution."""

from __future__ import annotations

import os
import logging
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
        response_format_mode: str = "json_schema",
        supports_json_schema: bool = True,
        supports_text_response_format: bool = True,
        headers: dict[str, str] | None = None,
        context_window_tokens: int | None = None,
        reserved_output_tokens: int | None = None,
        max_prompt_tokens: int | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("An API key or local provider token is required for real agent execution.")
        self._model = model or os.getenv("OPENAI_CODEX_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5"
        self._logger = logging.getLogger(__name__)
        self._response_format_mode = response_format_mode
        self._supports_json_schema = supports_json_schema
        self._supports_text_response_format = supports_text_response_format
        self._context_window_tokens = int(context_window_tokens or 0) or None
        self._reserved_output_tokens = int(reserved_output_tokens or 0) or 1024
        computed_prompt_limit = (
            max(512, self._context_window_tokens - self._reserved_output_tokens)
            if self._context_window_tokens
            else None
        )
        self._max_prompt_tokens = int(max_prompt_tokens or 0) or computed_prompt_limit
        self._client = AsyncOpenAI(
            api_key=resolved_api_key,
            base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
            timeout=timeout_seconds,
            default_headers=headers,
        )

    async def complete(self, messages: tuple[PromptMessage, ...]) -> str:
        """Execute the prompt through OpenAI and return message content."""

        response = await self._client.chat.completions.create(**self._build_payload(messages, stream=False))
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned an empty message content.")
        return content

    async def stream_complete(self, messages: tuple[PromptMessage, ...]):
        """Stream chat-completion text deltas as they arrive from OpenAI."""

        stream = await self._client.chat.completions.create(**self._build_payload(messages, stream=True))
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _build_payload(self, messages: tuple[PromptMessage, ...], *, stream: bool) -> dict[str, Any]:
        budgeted_messages, estimated_prompt_tokens, compression_applied = self._fit_messages_to_budget(messages)
        final_prompt_tokens = self._estimate_prompt_tokens(budgeted_messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": message.role.value, "content": message.content} for message in budgeted_messages],
            "stream": stream,
        }
        response_format = self._normalized_response_format()
        if response_format is not None:
            payload["response_format"] = response_format
        self._logger.info(
            "provider request metadata: model=%s stream=%s response_format=%s estimated_prompt_tokens=%s context_limit=%s reserved_output_tokens=%s final_prompt_tokens=%s compression_applied=%s",
            self._model,
            stream,
            response_format["type"] if response_format else "omitted",
            estimated_prompt_tokens,
            self._context_window_tokens,
            self._reserved_output_tokens,
            final_prompt_tokens,
            compression_applied,
        )
        return payload

    def _normalized_response_format(self) -> dict[str, str] | None:
        if self._response_format_mode == "json_schema" and self._supports_json_schema:
            return {"type": "json_schema"}
        if self._response_format_mode in {"json_schema", "text"} and self._supports_text_response_format:
            return {"type": "text"}
        return None

    def _fit_messages_to_budget(
        self,
        messages: tuple[PromptMessage, ...],
    ) -> tuple[tuple[PromptMessage, ...], int, bool]:
        estimated = self._estimate_prompt_tokens(messages)
        if not self._max_prompt_tokens or estimated <= self._max_prompt_tokens:
            return messages, estimated, False
        budgeted = list(messages)
        user_indexes = [index for index, item in enumerate(budgeted) if item.role.value == "user"]
        if user_indexes:
            index = user_indexes[-1]
            original = budgeted[index].content
            factor = max(0.25, self._max_prompt_tokens / max(estimated, 1))
            trimmed_chars = max(400, int(len(original) * factor))
            clipped = original[:trimmed_chars]
            if len(clipped) < len(original):
                clipped += "\n\n[Context trimmed automatically to fit model token budget.]"
            budgeted[index] = budgeted[index].model_copy(update={"content": clipped})
        final = tuple(budgeted)
        final_tokens = self._estimate_prompt_tokens(final)
        if self._max_prompt_tokens and final_tokens > self._max_prompt_tokens:
            raise ValueError(
                f"Prompt exceeded model context window after compression. estimated_prompt_tokens={final_tokens}, max_prompt_tokens={self._max_prompt_tokens}."
            )
        return final, estimated, True

    def _estimate_prompt_tokens(self, messages: tuple[PromptMessage, ...]) -> int:
        return sum(max(1, len(message.content) // 4) for message in messages)


OpenAIChatModelClient = OpenAICompatibleChatModelClient
