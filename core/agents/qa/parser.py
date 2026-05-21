"""QA runtime output parsing."""

import json
from typing import Any

from pydantic import ValidationError

from core.contracts.outputs import QAOutput


class QAOutputParser:
    """Parses raw model output into the QA output schema."""

    def parse(self, raw_output: str, agent_name: str) -> QAOutput:
        payload = self._load_json(raw_output)
        payload.setdefault("agent_name", agent_name)
        return QAOutput.model_validate(payload)

    def _load_json(self, raw_output: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise ValueError(f"QA output is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("QA output must be a JSON object.")
        return payload


def format_validation_error(exc: ValidationError) -> str:
    """Format validation errors for execution results."""

    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    )
