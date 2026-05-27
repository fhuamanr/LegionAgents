"""API schemas."""

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base API response model."""

    model_config = ConfigDict(extra="forbid")


class WorkflowStatus(StrEnum):
    """Workflow API status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HealthResponse(ApiModel):
    status: str
    service: str


class ProviderUpsertApiRequest(ApiModel):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    default_model: str = Field(min_length=1)
    status: str = Field(default="active", min_length=1)
    agent_models: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = 240
    context_window_tokens: int | None = 8192
    max_output_tokens: int | None = 1024
    reserved_output_tokens: int | None = 1024
    max_prompt_tokens: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    is_default: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderResponse(ApiModel):
    provider: dict[str, Any]


class ProviderListResponse(ApiModel):
    providers: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ProviderHealthResponse(ApiModel):
    checks: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ProviderConnectivityApiRequest(ApiModel):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    timeout_seconds: float | None = 60
    context_window_tokens: int | None = 8192
    max_output_tokens: int | None = 1024
    reserved_output_tokens: int | None = 1024
    max_prompt_tokens: int | None = None
    management_base_url: str | None = None
    inference_base_url: str | None = None
    lm_studio_auth_mode: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class ProviderConnectivityResponse(ApiModel):
    result: dict[str, Any]


class ProviderModelProfileUpdateRequest(ApiModel):
    context_window_tokens: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    supports_streaming: bool | None = None
    supports_json_mode: bool | None = None
    supports_tools: bool | None = None
    supports_embeddings: bool | None = None
    recommended_for_chat: bool | None = None
    recommended_for_agents: bool | None = None
    recommended_for_code: bool | None = None
    compact_mode_required: bool | None = None
    notes: str | None = None


class ProviderModelProfilesResponse(ApiModel):
    models: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ProviderModelAssignRequest(ApiModel):
    model_id: str = Field(min_length=1)


class LMStudioLoadModelRequest(ApiModel):
    model_id: str = Field(min_length=1)
    context_length: int | None = None
    max_output_tokens: int | None = None
    parallel_slots: int | None = None
    gpu_offload: int | None = None
    temperature: float | None = None
    streaming_enabled: bool | None = None
    flash_attention: bool = True
    echo_load_config: bool = True


class LMStudioUnloadModelRequest(ApiModel):
    model_id: str = Field(min_length=1)


class LMStudioDownloadModelRequest(ApiModel):
    model_id: str = Field(min_length=1)


class LMStudioDownloadStatusResponse(ApiModel):
    result: dict[str, Any] = Field(default_factory=dict)


class LMStudioRuntimeModelsResponse(ApiModel):
    available: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    loaded: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ProviderWorkflowPreflightRequest(ApiModel):
    workflow_mode: str = "full"
    required_agents: tuple[str, ...] = Field(default_factory=tuple)


class ProviderWorkflowPreflightResponse(ApiModel):
    ok: bool
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    recommendations: tuple[str, ...] = Field(default_factory=tuple)


class UserStoryUploadRequest(ApiModel):
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UploadResponse(ApiModel):
    upload_id: UUID
    title: str
    received_at: datetime


class TriggerWorkflowRequest(ApiModel):
    task: str = Field(min_length=1)
    upload_id: UUID | None = None
    thread_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResponse(ApiModel):
    workflow_id: UUID
    status: WorkflowStatus
    task: str
    thread_id: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentPlaygroundRunRequest(ApiModel):
    workflow_id: UUID | None = None
    agent_name: str = Field(min_length=1)
    input_source: str = Field(default="manual_prompt", min_length=1)
    prompt: str = ""
    uploaded_text: str | None = None
    previous_agent: str | None = None
    artifact_id: str | None = None
    provider_id: str | None = None
    model: str | None = None
    local_lm_studio_safe_mode: bool = False
    compact_mode_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentPlaygroundArtifactSummary(ApiModel):
    id: str
    workflow_id: UUID
    execution_id: UUID
    agent_name: str
    provider_id: str | None = None
    model_id: str | None = None
    raw_output: str = ""
    structured_output: dict[str, Any] = Field(default_factory=dict)
    handoff: str = ""
    execution_log: str = ""
    token_report: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AgentPlaygroundRunResponse(ApiModel):
    artifact: AgentPlaygroundArtifactSummary
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class AgentPlaygroundArtifactListResponse(ApiModel):
    artifacts: tuple[AgentPlaygroundArtifactSummary, ...] = Field(default_factory=tuple)


class AgentPlaygroundHandoffUpdateRequest(ApiModel):
    handoff: str = ""


class AgentPlaygroundWorkflowRunRequest(ApiModel):
    task: str = Field(min_length=1)
    enabled_agents: tuple[str, ...] = Field(default_factory=tuple)
    execution_mode: str = "sequential_auto"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionStatusResponse(ApiModel):
    workflow_id: UUID
    status: WorkflowStatus
    active_agent: str | None = None
    progress_percent: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionLogResponse(ApiModel):
    workflow_id: UUID
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class WorkflowTelemetryNode(ApiModel):
    id: str
    label: str
    agent_name: str
    status: WorkflowStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    retry_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTelemetryEdge(ApiModel):
    source: str
    target: str
    label: str | None = None
    condition: str | None = None
    is_loop: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTelemetryTimelineItem(ApiModel):
    id: str
    event_type: str
    agent_name: str | None = None
    message: str
    timestamp: datetime
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTelemetryResponse(ApiModel):
    workflow_id: UUID
    status: WorkflowStatus
    active_agent: str | None = None
    progress_percent: float
    duration_ms: int
    nodes: tuple[WorkflowTelemetryNode, ...] = Field(default_factory=tuple)
    edges: tuple[WorkflowTelemetryEdge, ...] = Field(default_factory=tuple)
    timeline: tuple[WorkflowTelemetryTimelineItem, ...] = Field(default_factory=tuple)
    mermaid: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStatusResponse(ApiModel):
    agents: dict[str, WorkflowStatus]


class ReportResponse(ApiModel):
    workflow_id: UUID
    kind: str
    content: dict[str, Any] = Field(default_factory=dict)


class WorkflowArtifactFile(ApiModel):
    name: str
    agent_name: str
    relative_path: str
    absolute_path: str
    size_bytes: int
    created_at: datetime
    preview: str = ""


class WorkflowArtifactListResponse(ApiModel):
    workflow_id: UUID
    files: tuple[WorkflowArtifactFile, ...] = Field(default_factory=tuple)


class ImproveExecutionRequest(ApiModel):
    artifact_root: str = Field(min_length=1)
    selected_agents: tuple[str, ...] = Field(default_factory=lambda: ("ba", "architect", "developer", "qa", "docs", "pr"))
    improvement_depth: str = Field(default="balanced", min_length=1)


class ImproveExecutionResponse(ApiModel):
    workflow_id: UUID
    improvements_path: str
    quality_report_path: str
    quality_metrics: dict[str, float] = Field(default_factory=dict)
    weaknesses: tuple[str, ...] = Field(default_factory=tuple)
    strengths: tuple[str, ...] = Field(default_factory=tuple)


class StoredUpload(ApiModel):
    upload_id: UUID = Field(default_factory=uuid4)
    title: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReviewerRequest(ApiModel):
    reviewer_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    email: str | None = None
    role: str | None = None


class CreateApprovalRequest(ApiModel):
    workflow_id: UUID
    gate_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    required_reviewers: tuple[ReviewerRequest, ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: str = "awaiting_approval"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionApiRequest(ApiModel):
    decision: str = Field(min_length=1)
    reviewer: ReviewerRequest
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalResponse(ApiModel):
    approval_id: UUID
    workflow_id: UUID
    gate_type: str
    status: str
    title: str
    description: str
    requested_by: str
    required_reviewers: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    agent_name: str | None = None
    thread_id: str | None = None
    pause_reason: str
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None = None
    decided_by: dict[str, Any] | None = None
    decision_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalListResponse(ApiModel):
    approvals: tuple[ApprovalResponse, ...] = Field(default_factory=tuple)


class WorkflowPauseResponse(ApiModel):
    workflow_id: UUID
    approval_id: UUID
    reason: str
    paused_at: datetime
    resume_token: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowResumeResponse(ApiModel):
    workflow_id: UUID
    approval_id: UUID
    can_resume: bool
    route_signal: str
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservabilitySnapshotResponse(ApiModel):
    snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkflowAnalyticsResponse(ApiModel):
    workflow_id: UUID
    analytics: dict[str, Any] = Field(default_factory=dict)


class AgentAnalyticsResponse(ApiModel):
    agents: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceConfigUpsertRequest(ApiModel):
    scope: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    markdown: str = ""
    agent_name: str | None = None
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GovernanceRollbackApiRequest(ApiModel):
    target_version: int = Field(ge=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None


class GovernanceConfigResponse(ApiModel):
    document: dict[str, Any]
    latest_version: dict[str, Any] | None = None
    reload_event: dict[str, Any] | None = None


class GovernanceConfigListResponse(ApiModel):
    documents: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceVersionListResponse(ApiModel):
    versions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class GovernanceReloadHistoryResponse(ApiModel):
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ChatConversationCreateRequest(ApiModel):
    title: str = Field(min_length=1)
    created_by: str = Field(default="workspace-user", min_length=1)


class ChatAttachmentUploadRequest(ApiModel):
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content: str | None = None
    uri: str | None = None
    path: str | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessageCreateRequest(ApiModel):
    content: str = Field(min_length=1)
    attachment_ids: tuple[UUID, ...] = Field(default_factory=tuple)
    trigger_workflow: bool = False
    resume_workflow: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatConversationResponse(ApiModel):
    conversation: dict[str, Any]


class ChatConversationListResponse(ApiModel):
    conversations: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class ChatAttachmentResponse(ApiModel):
    attachment: dict[str, Any]


class ChatMessageResponse(ApiModel):
    message: dict[str, Any]
    assistant_message: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None
    job_id: str | None = None
    status: str | None = None


class ChatEventListResponse(ApiModel):
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class PromptVariableRequest(ApiModel):
    name: str = Field(min_length=1)
    description: str | None = None
    required: bool = True
    default: str | None = None


class PromptUpsertApiRequest(ApiModel):
    name: str = Field(min_length=1)
    scope: str = Field(default="agent", min_length=1)
    agent_name: str | None = None
    markdown: str = ""
    variables: tuple[PromptVariableRequest, ...] = Field(default_factory=tuple)
    status: str = Field(default="draft", min_length=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptRollbackApiRequest(ApiModel):
    target_version: int = Field(ge=1)
    updated_by: str = Field(default="system", min_length=1)
    change_summary: str | None = None


class PromptPreviewApiRequest(ApiModel):
    markdown: str
    variables: dict[str, str] = Field(default_factory=dict)


class PromptTestApiRequest(ApiModel):
    prompt_id: UUID | None = None
    markdown: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    test_input: str = ""
    expected_output: str | None = None
    evaluator_notes: str | None = None


class PromptResponse(ApiModel):
    prompt: dict[str, Any]
    latest_version: dict[str, Any] | None = None


class PromptListResponse(ApiModel):
    prompts: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class PromptVersionListResponse(ApiModel):
    versions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class PromptPreviewResponse(ApiModel):
    preview: dict[str, Any]


class PromptTestResponse(ApiModel):
    result: dict[str, Any]


class PromptComparisonResponse(ApiModel):
    comparison: dict[str, Any]


class WorkspaceAgentConfigRequest(ApiModel):
    agent_name: str = Field(min_length=1)
    enabled: bool = True
    prompt_profile: str | None = None
    governance_profile: str | None = None
    max_retries: int = Field(default=2, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RepositoryBindingApiRequest(ApiModel):
    name: str = Field(min_length=1)
    provider: str = Field(default="local", min_length=1)
    uri: str | None = None
    path: str | None = None
    default_branch: str = "main"
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceCreateApiRequest(ApiModel):
    tenant_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    created_by: str = Field(default="workspace-admin", min_length=1)
    storage_root: str | None = None
    agents: tuple[WorkspaceAgentConfigRequest, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectCreateApiRequest(ApiModel):
    name: str = Field(min_length=1)
    description: str = ""
    repositories: tuple[RepositoryBindingApiRequest, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceResponse(ApiModel):
    workspace: dict[str, Any]


class WorkspaceListResponse(ApiModel):
    workspaces: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class WorkspaceProjectResponse(ApiModel):
    project: dict[str, Any]


class WorkspaceProjectListResponse(ApiModel):
    projects: tuple[dict[str, Any], ...] = Field(default_factory=tuple)


class WorkspaceIsolationResponse(ApiModel):
    isolation: dict[str, Any]


class TokenIssueApiRequest(ApiModel):
    subject: str = Field(min_length=1)
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    roles: tuple[str, ...] = Field(default_factory=tuple)
    permissions: tuple[str, ...] = Field(default_factory=tuple)
    expires_in_seconds: int = Field(default=3600, ge=60)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenIssueResponse(ApiModel):
    access_token: str
    token_type: str
    principal: dict[str, Any]


class AccessCheckApiRequest(ApiModel):
    required_permissions: tuple[str, ...] = Field(default_factory=tuple)
    any_permission: bool = False


class AccessCheckResponse(ApiModel):
    allowed: bool
    missing_permissions: tuple[str, ...] = Field(default_factory=tuple)
    granted_permissions: tuple[str, ...] = Field(default_factory=tuple)


class AuditEventCreateRequest(ApiModel):
    type: str = Field(min_length=1)
    action: str = Field(min_length=1)
    actor: str = "system"
    tenant_id: str | None = None
    workspace_id: UUID | None = None
    workflow_id: UUID | None = None
    agent_name: str | None = None
    resource: str | None = None
    outcome: str = "success"
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(ApiModel):
    event: dict[str, Any]


class AuditEventListResponse(ApiModel):
    events: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
