"""Base schemas shared by all platform contracts."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ContractVersion(StrEnum):
    """Supported contract versions."""

    V1 = "v1"


class ContractBaseModel(BaseModel):
    """Base model for immutable API-safe contracts."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class MutableContractBaseModel(BaseModel):
    """Base model for graph state contracts that evolve during execution."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )


class TraceMetadata(ContractBaseModel):
    """Cross-cutting trace metadata for distributed execution."""

    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    tags: tuple[str, ...] = Field(default_factory=tuple)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TimeStampedSchema(ContractBaseModel):
    """Immutable schema with UTC timestamps."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContractEnvelope(ContractBaseModel):
    """Generic envelope for versioned structured payloads."""

    id: UUID = Field(default_factory=uuid4)
    version: ContractVersion = ContractVersion.V1
    trace: TraceMetadata = Field(default_factory=TraceMetadata)
    payload: dict[str, Any] = Field(default_factory=dict)

