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
        payload, normalized_fields = _normalize_payload_for_model(self._output_model, payload, raw_output=raw_output)
        normalized_payload, pre_removed = _sanitize_for_model(self._output_model, payload)
        self.last_validation_metadata = {
            "json_extracted": bool(parse_meta.get("json_extracted", False)),
            "json_repaired": bool(parse_meta.get("json_repaired", False)),
            "repair_strategy": parse_meta.get("repair_strategy"),
            "repair_actions": parse_meta.get("repair_actions", []),
            "repair_candidates": parse_meta.get("repair_candidates", 0),
            "artifact_fallback_used": bool(parse_meta.get("artifact_fallback_used", False)),
            "extraction_strategy": parse_meta.get("extraction_strategy"),
            "fields_removed": pre_removed,
            "normalized_fields": normalized_fields,
            "normalization_applied": bool(normalized_fields),
            "sanitization_applied": bool(pre_removed),
            "validation_result": "started",
            "raw_output_size": len(raw_output),
            "schema_name": self._output_model.__name__,
            "repaired_output": parse_meta.get("repaired_output"),
            "normalized_output": normalized_payload,
            "repair_report": {
                "actions_applied": parse_meta.get("repair_actions", []),
                "fields_inferred": normalized_fields,
                "parse_warnings": parse_meta.get("parse_warnings", []),
                "normalization_actions": normalized_fields,
                "validation_warnings": [],
            },
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

    def _parse_payload(self, raw_output: str, *, strategy: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        if strategy == "ba_sections":
            payload = self._parse_ba_sections(raw_output)
            return payload, self._fallback_meta("ba_sections")
        if strategy == "developer_sections":
            try:
                payload, meta = self._parse_json(raw_output)
                return payload, meta
            except ValueError:
                payload = self._parse_developer_sections(raw_output)
                return payload, self._fallback_meta("developer_sections")
        if strategy == "qa_sections":
            try:
                payload, meta = self._parse_json(raw_output)
                return payload, meta
            except ValueError:
                payload = self._parse_qa_sections(raw_output)
                return payload, self._fallback_meta("qa_sections")
        if strategy == "docs_sections":
            try:
                payload, meta = self._parse_json(raw_output)
                return payload, meta
            except ValueError:
                payload = self._parse_docs_sections(raw_output)
                return payload, self._fallback_meta("docs_sections")
        if strategy == "architect_sections":
            try:
                payload, meta = self._parse_json(raw_output)
                return payload, meta
            except ValueError:
                payload = self._parse_architect_sections(raw_output)
                return payload, self._fallback_meta("architect_sections")
        if strategy == "pr_sections":
            try:
                payload, meta = self._parse_json(raw_output)
                return payload, meta
            except ValueError:
                payload = self._parse_pr_sections(raw_output)
                return payload, self._fallback_meta("pr_sections")
        try:
            return self._parse_json(raw_output)
        except ValueError:
            payload = self._parse_model_markdown_fallback(raw_output)
            if payload:
                return payload, self._fallback_meta("markdown_fallback")
            raise

    def _fallback_meta(self, strategy: str) -> dict[str, Any]:
        return {
            "json_extracted": False,
            "json_repaired": False,
            "repair_strategy": strategy,
            "repair_actions": [],
            "repair_candidates": 0,
            "artifact_fallback_used": True,
            "extraction_strategy": strategy,
            "parse_warnings": [],
            "repaired_output": None,
        }

    def _parse_json(self, raw_output: str) -> tuple[dict[str, Any], dict[str, Any]]:
        candidates = self._extract_json_candidates(raw_output)
        parse_errors: list[str] = []
        for extracted in candidates:
            repaired = False
            repaired_text: str | None = None
            actions: list[str] = []
            try:
                payload = json.loads(extracted)
            except json.JSONDecodeError as exc:
                repaired_text, actions = self._attempt_json_repair(extracted)
                if repaired_text is None:
                    parse_errors.append(str(exc))
                    continue
                try:
                    payload = json.loads(repaired_text)
                    repaired = True
                except json.JSONDecodeError as repaired_exc:
                    parse_errors.append(str(repaired_exc))
                    continue
            if not isinstance(payload, dict):
                continue
            return payload, {
                "json_extracted": extracted.strip() != raw_output.strip(),
                "json_repaired": repaired,
                "repair_strategy": "json_repair" if repaired else "json_direct",
                "repair_actions": actions,
                "repair_candidates": len(candidates),
                "artifact_fallback_used": False,
                "extraction_strategy": "candidate_scan",
                "parse_warnings": tuple(parse_errors[:3]),
                "repaired_output": repaired_text,
            }
        details = parse_errors[0] if parse_errors else "no recoverable JSON object found"
        raise ValueError(f"json_parse_error: Output is not valid JSON: {details}")

    def _extract_json_candidates(self, raw_output: str) -> list[str]:
        text = (raw_output or "").strip()
        if not text:
            return []
        candidates: list[str] = []
        fence_pattern = re.compile(r"```(?:json|javascript|js)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
        candidates.extend(match.group(1).strip() for match in fence_pattern.finditer(text) if match.group(1).strip())
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidates.append(text[start : end + 1].strip())
        stack = 0
        obj_start = -1
        for index, char in enumerate(text):
            if char == "{":
                if stack == 0:
                    obj_start = index
                stack += 1
            elif char == "}":
                if stack > 0:
                    stack -= 1
                    if stack == 0 and obj_start >= 0:
                        candidates.append(text[obj_start : index + 1].strip())
                        obj_start = -1
        if start >= 0 and stack > 0:
            candidates.append(text[start:].strip())
        candidates.append(text)
        seen: set[str] = set()
        deduped: list[str] = []
        for candidate in sorted(candidates, key=len, reverse=True):
            normalized = candidate.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _attempt_json_repair(self, text: str) -> tuple[str | None, list[str]]:
        candidate = text.strip()
        actions: list[str] = []
        if "```" in candidate:
            candidate = candidate.replace("```json", "").replace("```", "").strip()
            actions.append("strip_markdown_fences")
        patched = re.sub(r"/\*.*?\*/", "", candidate, flags=re.DOTALL)
        patched = re.sub(r"(^|\s)//.*?$", " ", patched, flags=re.MULTILINE)
        if patched != candidate:
            candidate = patched
            actions.append("remove_json_comments")
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
            actions.append("trim_to_object_bounds")
        patched = re.sub(r"(?<!\\)'([A-Za-z0-9_\- ]+?)'\s*:", r'"\1":', candidate)
        patched = re.sub(r":\s*'([^'\n\r]*)'", lambda m: ': "' + m.group(1).replace('"', '\\"') + '"', patched)
        if patched != candidate:
            candidate = patched
            actions.append("single_to_double_quotes")
        patched = re.sub(r",\s*([}\]])", r"\1", candidate)
        if patched != candidate:
            candidate = patched
            actions.append("remove_trailing_commas")
        patched = re.sub(r'([}\]"0-9])\s*(")', r"\1,\2", candidate)
        patched = re.sub(r'(")\s*({)', r"\1,\2", patched)
        if patched != candidate:
            candidate = patched
            actions.append("insert_missing_commas")
        if candidate.count("{") > candidate.count("}"):
            candidate = candidate + ("}" * (candidate.count("{") - candidate.count("}")))
            actions.append("close_missing_braces")
        if candidate.count("[") > candidate.count("]"):
            candidate = candidate + ("]" * (candidate.count("[") - candidate.count("]")))
            actions.append("close_missing_brackets")
        try:
            json.loads(candidate)
            return candidate, actions
        except json.JSONDecodeError:
            return None, actions

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

    def _parse_developer_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            return {"agent_name": "developer", "summary": "No developer output generated.", "code_changes": [], "tests": []}
        pattern = re.compile(r"```(?P<lang>[a-zA-Z0-9_+-]*)\n(?P<content>.*?)```", re.DOTALL)
        code_changes: list[dict[str, Any]] = []
        tests: list[dict[str, Any]] = []
        matches = list(pattern.finditer(text))
        if not matches:
            code_changes.append({"content": text})
        else:
            for index, match in enumerate(matches):
                content = match.group("content").strip()
                if not content:
                    continue
                before = text[max(0, match.start() - 240) : match.start()]
                path_matches = re.findall(r"(?im)(?:path|file)\s*[:=]\s*([^\n`]+)", before)
                path = path_matches[-1].strip() if path_matches else ""
                item = {"content": content}
                if path:
                    item["path"] = path
                lowered_content = content.lower()
                if (
                    ".test." in path.lower()
                    or "/test" in path.lower()
                    or "\\test" in path.lower()
                    or "test(" in lowered_content
                    or "describe(" in lowered_content
                ):
                    tests.append(item)
                else:
                    code_changes.append(item)
                if index >= 5:
                    break
        return {
            "agent_name": "developer",
            "summary": "Developer output parsed from markdown sections.",
            "code_changes": code_changes,
            "tests": tests,
        }

    def _parse_qa_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            return {}
        status = "needs_review"
        lowered = text.lower()
        if "pass" in lowered and "fail" not in lowered:
            status = "passed"
        if "fail" in lowered or "error" in lowered:
            status = "failed"
        return {
            "agent_name": "qa",
            "summary": text.splitlines()[0][:180] if text else "QA completed with limited structured output.",
            "status": status,
            "recommendations": [],
        }

    def _parse_docs_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            return {}
        return {
            "agent_name": "docs",
            "summary": text.splitlines()[0][:180] if text else "Docs agent completed with limited structured output.",
            "documents": [{"title": "Generated documentation", "audience": "engineering", "content_summary": text[:1200]}],
            "metadata": {"handoff": "Documentation needs review.", "documentation_markdown": text},
        }

    def _parse_pr_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            return {}
        return {
            "agent_name": "pr",
            "summary": text.splitlines()[0][:180] if text else "PR draft generated with limited structured output.",
            "title": "Draft PR",
            "description": text[:4000] or "PR content requires review.",
            "target_branch": "main",
            "source_branch": "codex/draft",
        }

    def _parse_architect_sections(self, raw_output: str) -> dict[str, Any]:
        text = raw_output.strip()
        if not text:
            return {}
        bullets = [line.lstrip("- ").strip() for line in text.splitlines() if line.strip().startswith("-")]
        decisions: list[dict[str, Any]] = []
        for index, bullet in enumerate(bullets[:5], start=1):
            decisions.append(
                {
                    "id": f"AD-{index}",
                    "title": bullet[:90] or f"Decision {index}",
                    "context": "Derived from architect markdown output.",
                    "decision": bullet[:240] or "Architecture decision captured from markdown output.",
                    "consequences": [],
                    "constraints": [],
                }
            )
        return {
            "agent_name": "architect",
            "summary": text.splitlines()[0][:180] if text else "Architect output parsed from markdown sections.",
            "decisions": decisions,
        }

    def _parse_model_markdown_fallback(self, raw_output: str) -> dict[str, Any]:
        model_name = self._output_model.__name__
        if model_name == "DeveloperOutput":
            return self._parse_developer_sections(raw_output)
        if model_name == "QAOutput":
            return self._parse_qa_sections(raw_output)
        if model_name == "DocsOutput":
            return self._parse_docs_sections(raw_output)
        if model_name == "ArchitectOutput":
            return self._parse_architect_sections(raw_output)
        if model_name == "BARequirementsOutput":
            return self._parse_ba_sections(raw_output)
        if model_name == "PullRequestOutput":
            return self._parse_pr_sections(raw_output)
        return {}

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


def _normalize_payload_for_model(
    model: type[BaseModel],
    payload: dict[str, Any],
    *,
    raw_output: str,
) -> tuple[dict[str, Any], list[str]]:
    if model.__name__ == "ArchitectOutput":
        return _normalize_architect_payload(payload, raw_output=raw_output)
    if model.__name__ == "QAOutput":
        return _normalize_qa_payload(payload, raw_output=raw_output)
    if model.__name__ == "DocsOutput":
        return _normalize_docs_payload(payload, raw_output=raw_output)
    if model.__name__ == "PullRequestOutput":
        return _normalize_pr_payload(payload, raw_output=raw_output)
    if model.__name__ != "DeveloperOutput":
        return payload, []
    normalized = dict(payload)
    added: list[str] = []
    if not normalized.get("agent_name"):
        normalized["agent_name"] = "developer"
        added.append("agent_name")
    code_changes = _normalize_code_changes(normalized.get("code_changes"), added)
    tests = _normalize_tests(normalized.get("tests"), added)
    normalized["code_changes"] = code_changes[:3]
    normalized["tests"] = tests[:3]
    if not str(normalized.get("summary", "")).strip():
        normalized["summary"] = f"Generated {len(normalized['code_changes'])} code change(s) and {len(normalized['tests'])} test(s)."
        added.append("summary")
    if not normalized.get("metadata"):
        normalized["metadata"] = {}
    metadata = normalized["metadata"] if isinstance(normalized.get("metadata"), dict) else {}
    metadata.setdefault("handoff", _build_developer_handoff(normalized))
    normalized["metadata"] = metadata
    if not normalized["code_changes"] and raw_output.strip():
        normalized["code_changes"] = [
            {
                "path": "generated/0.tsx",
                "change_type": "create",
                "description": "Generated implementation draft from developer output.",
                "content": raw_output.strip(),
            }
        ]
        added.extend(
            [
                "code_changes.0.path",
                "code_changes.0.change_type",
                "code_changes.0.description",
            ]
        )
    return normalized, added


def _normalize_code_changes(value: Any, added: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"content": item}
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        content = str(entry.get("content") or "").strip()
        path = str(entry.get("path") or "").strip()
        if not path:
            path = _infer_path_from_content(content, fallback=f"generated/{index}.tsx")
            entry["path"] = path
            added.append(f"code_changes.{index}.path")
        if not str(entry.get("change_type") or "").strip():
            entry["change_type"] = "create"
            added.append(f"code_changes.{index}.change_type")
        if not str(entry.get("description") or "").strip():
            entry["description"] = f"Implements changes for {path}."
            added.append(f"code_changes.{index}.description")
        entry["content"] = content or entry.get("content")
        normalized.append(entry)
    return normalized


def _normalize_tests(value: Any, added: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"content": item}
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        content = str(entry.get("content") or "").strip()
        path = str(entry.get("path") or "").strip()
        if not path:
            path = _infer_path_from_content(content, fallback=f"generated/{index}.test.tsx", is_test=True)
            entry["path"] = path
            added.append(f"tests.{index}.path")
        if not str(entry.get("test_type") or "").strip():
            entry["test_type"] = "unit"
            added.append(f"tests.{index}.test_type")
        if not str(entry.get("description") or "").strip():
            entry["description"] = f"Validates behavior for {path}."
            added.append(f"tests.{index}.description")
        entry["content"] = content or entry.get("content")
        normalized.append(entry)
    return normalized


def _infer_path_from_content(content: str, *, fallback: str, is_test: bool = False) -> str:
    candidate = ""
    match = re.search(r"(?im)(?:path|file)\s*[:=]\s*([^\n`]+)", content)
    if match:
        candidate = match.group(1).strip()
    if not candidate:
        func = re.search(r"(?m)^\s*(?:export\s+)?(?:function|class)\s+([A-Za-z_][A-Za-z0-9_]*)", content)
        if func:
            candidate = f"src/{func.group(1)}{'.test.tsx' if is_test else '.tsx'}"
    return candidate or fallback


def _build_developer_handoff(payload: dict[str, Any]) -> str:
    paths = [str(item.get("path", "")).strip() for item in payload.get("code_changes", []) if isinstance(item, dict)]
    tests = [str(item.get("path", "")).strip() for item in payload.get("tests", []) if isinstance(item, dict)]
    path_text = ", ".join(path for path in paths[:3] if path) or "implementation draft"
    test_text = ", ".join(path for path in tests[:3] if path) or "test draft"
    return f"Developer handoff: implemented {path_text}. Added tests: {test_text}."


def _normalize_qa_payload(payload: dict[str, Any], *, raw_output: str) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(payload or {})
    added: list[str] = []
    if not normalized:
        normalized = {
            "agent_name": "qa",
            "summary": "QA completed with limited structured output.",
            "findings": [],
            "test_reports": [],
            "execution_logs": [],
            "bug_summaries": [],
            "passed": False,
            "metadata": {"status": "needs_review"},
        }
        return normalized, ["agent_name", "summary", "fallback_object"]
    if not normalized.get("agent_name"):
        normalized["agent_name"] = "qa"
        added.append("agent_name")
    if not str(normalized.get("summary", "")).strip():
        summary_seed = str(normalized.get("status") or normalized.get("result") or "").strip()
        normalized["summary"] = summary_seed or "Short QA evaluation summary."
        added.append("summary")
    if not isinstance(normalized.get("findings"), list):
        normalized["findings"] = []
        added.append("findings")
    if not isinstance(normalized.get("test_reports"), list):
        normalized["test_reports"] = []
        added.append("test_reports")
    if not isinstance(normalized.get("execution_logs"), list):
        normalized["execution_logs"] = []
        added.append("execution_logs")
    if not isinstance(normalized.get("bug_summaries"), list):
        normalized["bug_summaries"] = []
        added.append("bug_summaries")
    if "passed" not in normalized:
        status = str(normalized.get("status", "")).strip().lower()
        normalized["passed"] = status in {"passed", "ok", "success"}
        added.append("passed")
    if not isinstance(normalized.get("metadata"), dict):
        normalized["metadata"] = {}
    normalized["metadata"].setdefault("raw_output_size", len(raw_output))
    return normalized, added


def _normalize_architect_payload(payload: dict[str, Any], *, raw_output: str) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(payload or {})
    added: list[str] = []
    if not normalized.get("agent_name"):
        normalized["agent_name"] = "architect"
        added.append("agent_name")
    if not str(normalized.get("summary", "")).strip():
        seed = raw_output.strip().splitlines()[0][:180] if raw_output.strip() else ""
        normalized["summary"] = seed or "Architect output generated with limited structured output."
        added.append("summary")
    if not isinstance(normalized.get("decisions"), list):
        normalized["decisions"] = []
        added.append("decisions")
    if not normalized["decisions"] and raw_output.strip():
        normalized["decisions"] = [
            {
                "id": "AD-1",
                "title": "Architecture outline",
                "context": "Recovered from unstructured architect output.",
                "decision": raw_output.strip()[:400],
                "consequences": [],
                "constraints": [],
            }
        ]
        added.append("decisions.0")
    return normalized, added


def _normalize_docs_payload(payload: dict[str, Any], *, raw_output: str) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(payload or {})
    added: list[str] = []
    if not normalized:
        normalized = {
            "agent_name": "docs",
            "summary": "Docs agent completed with limited structured output.",
            "documents": [],
            "metadata": {"handoff": "Documentation needs review.", "status": "needs_review"},
        }
        return normalized, ["agent_name", "summary", "fallback_object"]
    if not normalized.get("agent_name"):
        normalized["agent_name"] = "docs"
        added.append("agent_name")
    if not str(normalized.get("summary", "")).strip():
        seed = raw_output.strip().splitlines()[0][:180] if raw_output.strip() else ""
        normalized["summary"] = seed or "Documentation generated with limited structured output."
        added.append("summary")
    if not isinstance(normalized.get("documents"), list):
        normalized["documents"] = []
        added.append("documents")
    if not isinstance(normalized.get("metadata"), dict):
        normalized["metadata"] = {}
    normalized["metadata"].setdefault("handoff", "Docs completed with warnings.")
    if raw_output.strip():
        normalized["metadata"].setdefault("documentation_markdown", raw_output.strip())
    return normalized, added


def _normalize_pr_payload(payload: dict[str, Any], *, raw_output: str) -> tuple[dict[str, Any], list[str]]:
    normalized = dict(payload or {})
    added: list[str] = []
    if not normalized.get("agent_name"):
        normalized["agent_name"] = "pr"
        added.append("agent_name")
    if not str(normalized.get("summary", "")).strip():
        normalized["summary"] = "PR draft generated with limited structured output."
        added.append("summary")
    if not str(normalized.get("title", "")).strip():
        normalized["title"] = "Draft PR"
        added.append("title")
    if not str(normalized.get("description", "")).strip():
        normalized["description"] = raw_output.strip()[:4000] or "PR content requires review."
        added.append("description")
    if not str(normalized.get("target_branch", "")).strip():
        normalized["target_branch"] = "main"
        added.append("target_branch")
    if not str(normalized.get("source_branch", "")).strip():
        normalized["source_branch"] = "codex/draft"
        added.append("source_branch")
    return normalized, added
