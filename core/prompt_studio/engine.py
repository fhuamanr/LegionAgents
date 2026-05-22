"""Prompt testing, preview, comparison, and evaluation."""

import re

from core.contracts.prompt_studio import (
    PromptComparisonResult,
    PromptEvaluation,
    PromptPreview,
    PromptPreviewRequest,
    PromptTestRequest,
    PromptTestResult,
)


class PromptStudioEngine:
    """Pure prompt engineering utilities."""

    _variable_pattern = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

    async def preview(self, request: PromptPreviewRequest) -> PromptPreview:
        missing: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            value = request.variables.get(name)
            if value is None:
                missing.add(name)
                return match.group(0)
            return value

        rendered = self._variable_pattern.sub(replace, request.markdown)
        return PromptPreview(
            rendered=rendered,
            missing_variables=tuple(sorted(missing)),
            estimated_tokens=self.estimate_tokens(rendered),
            character_count=len(rendered),
        )

    async def test(self, request: PromptTestRequest, markdown: str) -> PromptTestResult:
        preview = await self.preview(PromptPreviewRequest(markdown=markdown, variables=request.variables))
        execution_preview = self._execution_preview(preview.rendered, request.test_input)
        evaluation = self._evaluate(preview, request)
        return PromptTestResult(
            preview=preview,
            execution_preview=execution_preview,
            evaluation=evaluation,
        )

    async def compare(
        self,
        left: str,
        right: str,
        left_version: int | None = None,
        right_version: int | None = None,
    ) -> PromptComparisonResult:
        left_lines = set(left.splitlines())
        right_lines = set(right.splitlines())
        added = tuple(sorted(right_lines - left_lines))
        removed = tuple(sorted(left_lines - right_lines))
        return PromptComparisonResult(
            left_version=left_version,
            right_version=right_version,
            added_lines=added,
            removed_lines=removed,
            changed_line_count=len(added) + len(removed),
            token_delta=self.estimate_tokens(right) - self.estimate_tokens(left),
        )

    def estimate_tokens(self, text: str) -> int:
        return max(1, round(len(text) / 4)) if text else 0

    def _execution_preview(self, rendered: str, test_input: str) -> str:
        sections = [rendered.strip()]
        if test_input.strip():
            sections.append(f"# Test Input\n\n{test_input.strip()}")
        return "\n\n".join(section for section in sections if section)

    def _evaluate(self, preview: PromptPreview, request: PromptTestRequest) -> PromptEvaluation:
        findings: list[str] = []
        score = 100.0
        if preview.missing_variables:
            score -= 30.0
            findings.append("Missing required variable values.")
        if preview.estimated_tokens > 4_000:
            score -= 15.0
            findings.append("Prompt preview is large and may need compression.")
        if request.expected_output and request.expected_output.lower() not in preview.rendered.lower():
            score -= 10.0
            findings.append("Expected output hint is not represented in the prompt preview.")
        if "{{" in preview.rendered:
            score -= 10.0
            findings.append("Unresolved template placeholders remain.")
        score = max(0.0, score)
        return PromptEvaluation(
            score=score,
            passed=score >= 70.0,
            findings=tuple(findings),
            metadata={"estimated_tokens": preview.estimated_tokens},
        )
