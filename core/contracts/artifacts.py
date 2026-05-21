"""Artifact contracts emitted by agents."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactKind(StrEnum):
    """Supported artifact families."""

    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    SOURCE_CODE = "source_code"
    TEST_REPORT = "test_report"
    DOCUMENTATION = "documentation"
    PULL_REQUEST = "pull_request"
    DIAGRAM = "diagram"
    GENERIC = "generic"


class Artifact(BaseModel):
    """Structured reference to an output produced during a workflow."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: ArtifactKind = ArtifactKind.GENERIC
    name: str = Field(min_length=1)
    producer_agent: str = Field(min_length=1)
    path: Path | None = None
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

