"""Chat instruction intent parsing for workflow execution."""

from __future__ import annotations

import re

from core.contracts.chat import ChatWorkflowIntent, ChatWorkflowType, WorkspaceAttachment


class ChatWorkflowIntentParser:
    """Classifies user chat instructions into executable workflow types."""

    _repository_pattern = re.compile(
        r"(https?://\S+|git@\S+|(?:[A-Za-z]:\\|/)[^\s]+)",
        flags=re.IGNORECASE,
    )

    _feature_terms = ("feature", "story", "implement", "build", "add", "create", "generate")
    _bugfix_terms = ("bug", "fix", "defect", "error", "broken", "failure", "regression")
    _refactor_terms = ("refactor", "cleanup", "clean up", "restructure", "simplify", "technical debt")
    _repository_terms = ("analyze repo", "repository analysis", "scan repo", "inspect repo", "architecture detection")
    _resume_terms = ("resume", "continue workflow", "continue execution", "recover workflow")

    async def parse(
        self,
        instruction: str,
        attachments: tuple[WorkspaceAttachment, ...] = tuple(),
    ) -> ChatWorkflowIntent:
        """Parse a user instruction and attached references into workflow intent."""

        text = instruction.strip()
        normalized = text.lower()
        references = self._repository_references(text, attachments)
        resume_requested = any(term in normalized for term in self._resume_terms)
        workflow_type, reason, confidence = self._classify(normalized, references)
        should_trigger = resume_requested or confidence >= 0.45 or bool(references)
        task = self._build_task(text, workflow_type, attachments)
        return ChatWorkflowIntent(
            workflow_type=workflow_type,
            should_trigger_workflow=should_trigger,
            resume_requested=resume_requested,
            confidence=confidence,
            normalized_task=task,
            repository_references=references,
            reasons=(reason,),
            metadata={
                "attachment_count": len(attachments),
                "has_repository_reference": bool(references),
            },
        )

    def _classify(
        self,
        normalized: str,
        references: tuple[str, ...],
    ) -> tuple[ChatWorkflowType, str, float]:
        if any(term in normalized for term in self._repository_terms) or (
            references and "repo" in normalized
        ):
            return ChatWorkflowType.REPOSITORY_ANALYSIS, "repository_analysis_terms", 0.9
        if any(term in normalized for term in self._bugfix_terms):
            return ChatWorkflowType.BUGFIX, "bugfix_terms", 0.85
        if any(term in normalized for term in self._refactor_terms):
            return ChatWorkflowType.REFACTOR, "refactor_terms", 0.85
        if any(term in normalized for term in self._feature_terms):
            return ChatWorkflowType.FEATURE, "feature_terms", 0.8
        return ChatWorkflowType.GENERAL_DELIVERY, "general_delivery_default", 0.35

    def _repository_references(
        self,
        instruction: str,
        attachments: tuple[WorkspaceAttachment, ...],
    ) -> tuple[str, ...]:
        references = list(self._repository_pattern.findall(instruction))
        for attachment in attachments:
            if attachment.uri:
                references.append(attachment.uri)
            if attachment.path:
                references.append(str(attachment.path))
        return tuple(dict.fromkeys(references))

    def _build_task(
        self,
        instruction: str,
        workflow_type: ChatWorkflowType,
        attachments: tuple[WorkspaceAttachment, ...],
    ) -> str:
        sections = [
            f"Workflow type: {workflow_type.value}",
            f"User instruction: {instruction}",
        ]
        if attachments:
            rendered = "\n".join(
                f"- {attachment.kind.value}: {attachment.name}"
                + (f" ({attachment.uri})" if attachment.uri else "")
                for attachment in attachments
            )
            sections.append(f"Attached context:\n{rendered}")
        return "\n\n".join(sections)
