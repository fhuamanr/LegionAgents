"""Structured output validation."""

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

TOutput = TypeVar("TOutput", bound=BaseModel)


class OutputValidator(ABC, Generic[TOutput]):
    """Validates raw agent output into a structured output schema."""

    @abstractmethod
    async def validate(self, raw_output: str) -> TOutput:
        """Validate and return structured output."""


class PydanticOutputValidator(OutputValidator[TOutput]):
    """Pydantic-backed structured output validator."""

    def __init__(self, output_model: type[TOutput]) -> None:
        self._output_model = output_model

    async def validate(self, raw_output: str) -> TOutput:
        payload = self._parse_json(raw_output)
        try:
            return self._output_model.model_validate(payload)
        except ValidationError as exc:
            raise ValueError(self._format_validation_error(exc)) from exc

    def _parse_json(self, raw_output: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Output is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Output must be a JSON object.")
        return payload

    def _format_validation_error(self, exc: ValidationError) -> str:
        return "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )

