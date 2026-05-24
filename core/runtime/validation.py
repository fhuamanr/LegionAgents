"""Structured output validation."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

TOutput = TypeVar("TOutput", bound=BaseModel)


class OutputValidator(ABC, Generic[TOutput]):
    """Validates raw agent output into a structured output schema."""

    @abstractmethod
    async def validate(self, raw_output: str, *, strategy: str | None = None) -> TOutput:
        """Validate and return structured output."""


class PydanticOutputValidator(OutputValidator[TOutput]):
    """Pydantic-backed structured output validator."""

    def __init__(self, output_model: type[TOutput]) -> None:
        self._output_model = output_model
        self.last_validation_metadata: dict[str, Any] = {}

    async def validate(self, raw_output: str, *, strategy: str | None = None) -> TOutput:
        payload, parse_meta = self._parse_payload(raw_output, strategy=strategy)
        normalized_payload, pre_removed = _sanitize_for_model(self._output_model, payload)
        self.last_validation_metadata = {
            "json_extracted": parse_meta["json_extracted"],
            "json_repaired": parse_meta["json_repaired"],
            "fields_removed": pre_removed,
            "sanitization_applied": bool(pre_removed),
            "validation_result": "started",
            "raw_output_size": len(raw_output),
            "schema_name": self._output_model.__name__,
        }
        try:
            validated = self._output_model.model_validate(normalized_payload)
            self.last_validation_metadata["validation_result"] = "ok"
            return validated
        except ValidationError as exc:
            if pre_removed:
                try:
                    validated = self._output_model.model_validate(normalized_payload)
                    self.last_validation_metadata["validation_result"] = "ok_after_sanitize"
                    return validated
                except ValidationError:
                    pass
            self.last_validation_metadata["validation_result"] = "schema_contract_error"
            raise ValueError(f"schema_contract_error: {self._format_validation_error(exc)}") from exc

    def _parse_payload(self, raw_output: str, *, strategy: str | None = None) -> tuple[dict[str, Any], dict[str, bool]]:
        if strategy == "ba_sections":
            payload = self._parse_ba_sections(raw_output)
            return payload, {"json_extracted": False, "json_repaired": False}
        return self._parse_json(raw_output)

    def _parse_json(self, raw_output: str) -> tuple[dict[str, Any], dict[str, bool]]:
        extracted = self._extract_json_block(raw_output)
        repaired = False
        try:
            payload = json.loads(extracted)
        except json.JSONDecodeError as exc:
            repaired_text = self._attempt_json_repair(extracted)
            if repaired_text is None:
                raise ValueError(f"json_parse_error: Output is not valid JSON: {exc}") from exc
            repaired = True
            payload = json.loads(repaired_text)
        if not isinstance(payload, dict):
            raise ValueError("json_parse_error: Output must be a JSON object.")
        return payload, {"json_extracted": extracted.strip() != raw_output.strip(), "json_repaired": repaired}

    def _extract_json_block(self, raw_output: str) -> str:
        text = raw_output.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
                return "\n".join(lines[1:-1]).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return text[start : end + 1]
        return text

    def _attempt_json_repair(self, text: str) -> str | None:
        candidate = text.strip()
        candidate = candidate.replace("```json", "").replace("```", "").strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
        if candidate.count("{") > candidate.count("}"):
            candidate = candidate + ("}" * (candidate.count("{") - candidate.count("}")))
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            return None

    def _parse_ba_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        sections = {
            "NORMALIZED_REQUIREMENT:": "",
            "USER_STORIES:": "",
            "ASSUMPTIONS:": "",
            "RISKS:": "",
            "DEPENDENCIES:": "",
        }
        current: str | None = None
        buffers: dict[str, list[str]] = {key: [] for key in sections}
        for line in text.splitlines():
            marker = line.strip().upper()
            if marker in sections:
                current = marker
                continue
            if current is not None:
                buffers[current].append(line.rstrip())
        normalized = " ".join(item.strip() for item in buffers["NORMALIZED_REQUIREMENT:"] if item.strip()).strip()
        assumptions = [line.lstrip("- ").strip() for line in buffers["ASSUMPTIONS:"] if line.strip()]
        risks = [line.lstrip("- ").strip() for line in buffers["RISKS:"] if line.strip()]
        dependencies = [line.lstrip("- ").strip() for line in buffers["DEPENDENCIES:"] if line.strip()]

        stories: list[dict[str, Any]] = []
        current_story: dict[str, Any] | None = None
        ac_index = 1
        for raw_line in buffers["USER_STORIES:"]:
            line = raw_line.strip()
            if not line:
                continue
            if re.match(r"^\d+\.\s+", line):
                if current_story is not None:
                    stories.append(current_story)
                story_text = re.split(r"^\d+\.\s+", line, maxsplit=1)[1].strip()
                sid = f"US-{len(stories) + 1}"
                current_story = {
                    "id": sid,
                    "title": story_text[:80] or sid,
                    "narrative": story_text or f"As a user, I want {sid}",
                    "acceptance_criteria": [],
                }
                ac_index = 1
                continue
            if current_story is None:
                continue
            stripped = line.replace("AC:", "").lstrip("- ").strip()
            if stripped:
                current_story["acceptance_criteria"].append(
                    {
                        "id": f"{current_story['id']}-AC-{ac_index}",
                        "scenario": stripped[:120],
                        "expected_result": stripped[:160],
                    }
                )
                ac_index += 1
        if current_story is not None:
            stories.append(current_story)
        return {
            "agent_name": "ba",
            "summary": normalized[:180] or "BA requirements extracted.",
            "normalized_requirement": normalized[:500],
            "user_stories": stories[:3],
            "assumptions": assumptions[:3],
            "risks": [{"id": f"R-{index+1}", "title": risk[:80] or f"Risk {index+1}", "severity": "medium", "description": risk[:240]} for index, risk in enumerate(risks[:3])],
            "dependencies": [{"name": dep[:80] or f"Dependency {index+1}", "description": dep[:200], "blocking": True} for index, dep in enumerate(dependencies[:3])],
        }

    def _format_validation_error(self, exc: ValidationError) -> str:
        return "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )


def _sanitize_for_model(model: type[BaseModel], payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    removed: list[str] = []
    fields = model.model_fields
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in fields:
            removed.append(key)
            continue
        field = fields[key]
        annotation = field.annotation
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", ())
        if isinstance(value, dict) and isinstance(annotation, type) and issubclass(annotation, BaseModel):
            child, child_removed = _sanitize_for_model(annotation, value)
            sanitized[key] = child
            removed.extend([f"{key}.{path}" for path in child_removed])
            continue
        if isinstance(value, (list, tuple)) and origin in {tuple, list} and args:
            item_type = args[0]
            cleaned_items: list[Any] = []
            for index, item in enumerate(value):
                if isinstance(item, dict) and isinstance(item_type, type) and issubclass(item_type, BaseModel):
                    child, child_removed = _sanitize_for_model(item_type, item)
                    cleaned_items.append(child)
                    removed.extend([f"{key}.{index}.{path}" for path in child_removed])
                else:
                    cleaned_items.append(item)
            sanitized[key] = cleaned_items
            continue
        sanitized[key] = value

    if model.__name__ == "BARequirementsOutput":
        stories = list(sanitized.get("user_stories", []))
        stories = stories[:3]
        for story in stories:
            if isinstance(story, dict):
                criteria = list(story.get("acceptance_criteria", []))
                story["acceptance_criteria"] = criteria[:3]
        sanitized["user_stories"] = stories
        sanitized["assumptions"] = list(sanitized.get("assumptions", []))[:3]
        sanitized["risks"] = list(sanitized.get("risks", []))[:3]
        sanitized["dependencies"] = list(sanitized.get("dependencies", []))[:3]
    return sanitized, removed
