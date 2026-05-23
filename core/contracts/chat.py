"""Contracts for AI workspace chat and uploads."""

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from core.contracts.base import ContractBaseModel


class ChatRole(StrEnum):
    """Workspace chat message role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    WORKFLOW = "workflow"


class WorkspaceAttachmentKind(StrEnum):
    """Supported workspace attachment kinds."""

    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TEXT = "text"
    URL = "url"
    GIT_REPOSITORY = "git_repository"
    REPOSITORY_PATH = "repository_path"


class ChatEventType(StrEnum):
    """Streaming chat event types."""

    MESSAGE_CREATED = "message_created"
    ATTACHMENT_UPLOADED = "attachment_uploaded"
    WORKFLOW_TRIGGERED = "workflow_triggered"
    EXECUTION_PROGRESS = "execution_progress"
    ERROR = "error"


class ChatMessageStatus(StrEnum):
    """Workspace chat message processing status."""

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChatWorkflowType(StrEnum):
    """Workflow families that can be initiated from chat instructions."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    REPOSITORY_ANALYSIS = "repository_analysis"
    GENERAL_DELIVERY = "general_delivery"


class ChatWorkflowIntent(ContractBaseModel):
    """Parsed workflow intent from a user chat instruction."""

    workflow_type: ChatWorkflowType
    should_trigger_workflow: bool = False
    resume_requested: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)
    normalized_task: str = Field(min_length=1)
    repository_references: tuple[str, ...] = Field(default_factory=tuple)
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAttachment(ContractBaseModel):
    """Uploaded or referenced workspace input."""

    id: UUID = Field(default_factory=uuid4)
    kind: WorkspaceAttachmentKind
    name: str = Field(min_length=1)
    content: str | None = None
    uri: str | None = None
    path: Path | None = None
    content_type: str | None = None
    size_bytes: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessage(ContractBaseModel):
    """Persisted workspace chat message."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: ChatRole
    content: str = ""
    attachment_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    workflow_id: UUID | None = None
    status: ChatMessageStatus = ChatMessageStatus.COMPLETED
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatConversation(ContractBaseModel):
    """Persisted workspace conversation."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1)
    created_by: str = Field(default="workspace-user", min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: tuple[ChatMessage, ...] = Field(default_factory=tuple)
    attachments: tuple[WorkspaceAttachment, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatEvent(ContractBaseModel):
    """WebSocket-ready workspace chat event."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    type: ChatEventType
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatAttachmentUpload(ContractBaseModel):
    """Attachment upload or reference request."""

    kind: WorkspaceAttachmentKind
    name: str = Field(min_length=1)
    content: str | None = None
    uri: str | None = None
    path: Path | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageRequest(ContractBaseModel):
    """Create chat message request."""

    content: str = Field(min_length=1)
    attachment_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    trigger_workflow: bool = False
    resume_workflow: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
