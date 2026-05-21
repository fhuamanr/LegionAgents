"""Developer runtime contracts."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel
from core.contracts.outputs import OutputContract


class DeveloperCapability(StrEnum):
    """Developer runtime capabilities."""

    CODE_GENERATION = "code_generation"
    REPOSITORY_ANALYSIS = "repository_analysis"
    TEST_GENERATION = "test_generation"
    REFACTORING_SUGGESTIONS = "refactoring_suggestions"
    COMMIT_MESSAGE_GENERATION = "commit_message_generation"
    PR_DRAFT_GENERATION = "pr_draft_generation"


class DeveloperRuntimeConfig(ContractBaseModel):
    """Configuration for the developer agent runtime."""

    agent_name: str = "developer"
    context_path: Path
    repository_path: Path = Field(default_factory=Path.cwd)
    output_contract: OutputContract
    max_context_token_hint: int | None = Field(default=None, ge=1)
    additional_instructions: tuple[str, ...] = Field(default_factory=tuple)
    required_rule_files: tuple[str, ...] = (
        "gravity.md",
        "anti-gravity.md",
        "coding-standards.md",
        "architecture.md",
        "forbidden.md",
        "naming.md",
        "testing.md",
        "security.md",
    )
    capabilities: tuple[DeveloperCapability, ...] = (
        DeveloperCapability.CODE_GENERATION,
        DeveloperCapability.REPOSITORY_ANALYSIS,
        DeveloperCapability.TEST_GENERATION,
        DeveloperCapability.REFACTORING_SUGGESTIONS,
        DeveloperCapability.COMMIT_MESSAGE_GENERATION,
        DeveloperCapability.PR_DRAFT_GENERATION,
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryFileSummary(ContractBaseModel):
    """Summary of a repository file visible to the developer agent."""

    path: str = Field(min_length=1)
    suffix: str
    size_bytes: int = Field(ge=0)


class RepositoryAnalysis(ContractBaseModel):
    """Repository structure analysis for prompt context."""

    root_path: Path
    files: tuple[RepositoryFileSummary, ...] = Field(default_factory=tuple)
    directories: tuple[str, ...] = Field(default_factory=tuple)
    detected_languages: tuple[str, ...] = Field(default_factory=tuple)
    test_paths: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)
