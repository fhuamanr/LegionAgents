export type AgentKey = "ba" | "architect" | "developer" | "qa" | "docs" | "pr";

export type AgentStatus = "idle" | "running" | "blocked" | "completed" | "failed";

export type WorkflowStageStatus =
  | "pending"
  | "running"
  | "completed"
  | "rejected"
  | "failed";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type ApprovalGateType = "manual_review" | "retry_approval" | "pr_approval" | "qa_override" | "release_approval";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled" | "expired";

export interface AgentSummary {
  readonly key: AgentKey;
  readonly name: string;
  readonly status: AgentStatus;
  readonly currentTask: string;
  readonly lastEventAt: string;
  readonly retryCount: number;
}

export interface WorkflowStage {
  readonly id: AgentKey;
  readonly label: string;
  readonly status: WorkflowStageStatus;
  readonly startedAt?: string;
  readonly completedAt?: string;
  readonly metadata: Record<string, string | number | boolean>;
}

export interface ExecutionEvent {
  readonly id: string;
  readonly type:
    | "agent_started"
    | "agent_completed"
    | "agent_failed"
    | "retry_started"
    | "QA_failed"
    | "PR_generated"
    | "docs_generated";
  readonly agent: AgentKey;
  readonly message: string;
  readonly timestamp: string;
  readonly severity: Severity;
}

export interface TimelineItem {
  readonly id: string;
  readonly title: string;
  readonly description: string;
  readonly timestamp: string;
  readonly status: WorkflowStageStatus;
}

export interface WorkflowTelemetryNode {
  readonly id: AgentKey;
  readonly label: string;
  readonly agentName: AgentKey;
  readonly status: "pending" | "running" | "paused" | "completed" | "failed";
  readonly startedAt?: string;
  readonly completedAt?: string;
  readonly durationMs?: number;
  readonly retryCount: number;
  readonly metadata: Record<string, string | number | boolean>;
}

export interface WorkflowTelemetryEdge {
  readonly source: AgentKey;
  readonly target: AgentKey;
  readonly label?: string;
  readonly condition?: string;
  readonly isLoop: boolean;
  readonly metadata: Record<string, string | number | boolean>;
}

export interface WorkflowTelemetryTimelineItem {
  readonly id: string;
  readonly eventType: string;
  readonly agentName?: AgentKey;
  readonly message: string;
  readonly timestamp: string;
  readonly durationMs?: number;
  readonly metadata: Record<string, string | number | boolean>;
}

export interface WorkflowTelemetrySnapshot {
  readonly workflowId: string;
  readonly status: "pending" | "running" | "paused" | "completed" | "failed";
  readonly activeAgent?: AgentKey;
  readonly progressPercent: number;
  readonly durationMs: number;
  readonly nodes: readonly WorkflowTelemetryNode[];
  readonly edges: readonly WorkflowTelemetryEdge[];
  readonly timeline: readonly WorkflowTelemetryTimelineItem[];
  readonly mermaid: string;
  readonly metadata: Record<string, string | number | boolean>;
}

export interface LogEntry {
  readonly id: string;
  readonly timestamp: string;
  readonly level: "debug" | "info" | "warning" | "error";
  readonly source: string;
  readonly message: string;
}

export interface QaBug {
  readonly id: string;
  readonly title: string;
  readonly severity: Severity;
  readonly status: "open" | "triaged" | "fixed" | "accepted";
  readonly evidence: string;
}

export interface QaReport {
  readonly executionId: string;
  readonly status: "passed" | "failed" | "running";
  readonly coveragePercent: number;
  readonly unitTests: number;
  readonly integrationTests: number;
  readonly browserTests: number;
  readonly bugs: readonly QaBug[];
  readonly screenshots: readonly ScreenshotArtifact[];
}

export interface ScreenshotArtifact {
  readonly id: string;
  readonly title: string;
  readonly path: string;
  readonly capturedAt: string;
}

export interface DocumentationArtifact {
  readonly id: string;
  readonly title: string;
  readonly status: "draft" | "generated" | "published";
  readonly updatedAt: string;
  readonly summary: string;
}

export interface PullRequestSummary {
  readonly id: string;
  readonly title: string;
  readonly status: "draft" | "ready" | "merged";
  readonly branch: string;
  readonly target: string;
  readonly changedFiles: number;
  readonly riskLevel: Severity;
  readonly summary: string;
}

export interface ReviewerSummary {
  readonly reviewerId: string;
  readonly displayName: string;
  readonly role?: string;
}

export interface ApprovalGate {
  readonly approvalId: string;
  readonly workflowId: string;
  readonly gateType: ApprovalGateType;
  readonly status: ApprovalStatus;
  readonly title: string;
  readonly description: string;
  readonly requestedBy: string;
  readonly requiredReviewers: readonly ReviewerSummary[];
  readonly pauseReason: string;
  readonly createdAt: string;
  readonly decidedAt?: string;
  readonly decisionReason?: string;
}

export interface TokenUsageSummary {
  readonly promptTokens: number;
  readonly completionTokens: number;
  readonly totalTokens: number;
}

export interface PromptTelemetrySummary {
  readonly messageCount: number;
  readonly characterCount: number;
  readonly estimatedTokens: number;
}

export interface AgentAnalyticsSummary {
  readonly agentName: string;
  readonly executionsStarted: number;
  readonly executionsCompleted: number;
  readonly failures: number;
  readonly retries: number;
  readonly qaRejections: number;
  readonly averageExecutionTimeMs: number;
  readonly tokenUsage: TokenUsageSummary;
  readonly promptTelemetry: PromptTelemetrySummary;
}

export interface WorkflowAnalyticsSummary {
  readonly workflowId: string;
  readonly durationMs: number;
  readonly agentCount: number;
  readonly retries: number;
  readonly failures: number;
  readonly qaRejectionRate: number;
  readonly tokenUsage: TokenUsageSummary;
  readonly promptTelemetry: PromptTelemetrySummary;
}

export interface ObservabilitySummary {
  readonly workflow: WorkflowAnalyticsSummary;
  readonly agents: readonly AgentAnalyticsSummary[];
  readonly metrics: readonly string[];
  readonly exporters: {
    readonly opentelemetryReady: boolean;
    readonly datadogReady: boolean;
    readonly prometheusReady: boolean;
    readonly grafanaReady: boolean;
  };
}

export type GovernanceConfigScope = "global" | "agent";

export type GovernanceConfigKind =
  | "gravity"
  | "anti_gravity"
  | "personality"
  | "prompt"
  | "coding_standards"
  | "qa_policy";

export interface GovernanceConfigDocument {
  readonly id: string;
  readonly scope: GovernanceConfigScope;
  readonly kind: GovernanceConfigKind;
  readonly name: string;
  readonly markdown: string;
  readonly agentName?: string;
  readonly version: number;
  readonly updatedBy: string;
  readonly updatedAt: string;
}

export interface GovernanceConfigVersion {
  readonly id: string;
  readonly documentId: string;
  readonly version: number;
  readonly markdown: string;
  readonly changedBy: string;
  readonly changeSummary?: string;
  readonly createdAt: string;
}

export type ChatRole = "user" | "assistant" | "system" | "workflow";

export type WorkspaceAttachmentKind =
  | "pdf"
  | "docx"
  | "markdown"
  | "text"
  | "url"
  | "git_repository"
  | "repository_path";

export interface WorkspaceAttachmentSummary {
  readonly id: string;
  readonly kind: WorkspaceAttachmentKind;
  readonly name: string;
  readonly uri?: string;
  readonly path?: string;
  readonly sizeBytes: number;
}

export interface WorkspaceChatMessage {
  readonly id: string;
  readonly role: ChatRole;
  readonly content: string;
  readonly attachmentIds: readonly string[];
  readonly workflowId?: string;
  readonly createdAt: string;
}

export interface WorkspaceConversationSummary {
  readonly id: string;
  readonly title: string;
  readonly messages: readonly WorkspaceChatMessage[];
  readonly attachments: readonly WorkspaceAttachmentSummary[];
  readonly updatedAt: string;
}

export interface DashboardSnapshot {
  readonly workflowId: string;
  readonly agents: readonly AgentSummary[];
  readonly stages: readonly WorkflowStage[];
  readonly events: readonly ExecutionEvent[];
  readonly timeline: readonly TimelineItem[];
  readonly logs: readonly LogEntry[];
  readonly qaReport: QaReport;
  readonly docs: readonly DocumentationArtifact[];
  readonly pullRequest: PullRequestSummary;
  readonly approvals: readonly ApprovalGate[];
  readonly observability: ObservabilitySummary;
  readonly governance: {
    readonly documents: readonly GovernanceConfigDocument[];
    readonly versions: readonly GovernanceConfigVersion[];
  };
  readonly workspace: {
    readonly conversations: readonly WorkspaceConversationSummary[];
  };
  readonly visualization: WorkflowTelemetrySnapshot;
  readonly mermaid: string;
}
