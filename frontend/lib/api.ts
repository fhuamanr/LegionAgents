import { normalizeWorkflowTelemetry } from "./realtime";
import type {
  DashboardSnapshot,
  GovernanceConfigDocument,
  GovernanceConfigVersion,
  LlmProviderHealthCheck,
  LlmProviderSummary,
  PromptDocument,
  PromptTestSummary,
  PromptVersion,
  WorkspaceConversationSummary,
  WorkflowTelemetrySnapshot,
} from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const internalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;

function resolvedApiBaseUrl(): string | undefined {
  if (typeof window === "undefined" && internalApiBaseUrl) {
    return internalApiBaseUrl;
  }
  return apiBaseUrl;
}

async function requestJson<T>(path: string): Promise<T> {
  const baseUrl = resolvedApiBaseUrl();
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  if (!resolvedApiBaseUrl()) {
    return emptyDashboardSnapshot();
  }

  try {
    return await requestJson<DashboardSnapshot>("/dashboard/snapshot");
  } catch {
    return emptyDashboardSnapshot();
  }
}

export async function getWorkflowTelemetry(workflowId: string): Promise<WorkflowTelemetrySnapshot> {
  if (!resolvedApiBaseUrl()) {
    return emptyDashboardSnapshot().visualization;
  }

  try {
    return normalizeWorkflowTelemetry(await requestJson<Record<string, unknown>>(`/executions/${workflowId}/telemetry`));
  } catch {
    return emptyDashboardSnapshot().visualization;
  }
}

export async function getProviderManagementSnapshot(): Promise<{
  providers: readonly LlmProviderSummary[];
  checks: readonly LlmProviderHealthCheck[];
}> {
  if (!resolvedApiBaseUrl()) {
    return { providers: [], checks: [] };
  }

  const providersResponse = await requestJson<{ providers: readonly Record<string, unknown>[] }>("/providers");
  let healthResponse: { checks: readonly Record<string, unknown>[] } = { checks: [] };
  try {
    healthResponse = await requestJson<{ checks: readonly Record<string, unknown>[] }>("/providers/health");
  } catch {
    healthResponse = { checks: [] };
  }
  return {
    providers: providersResponse.providers.map(normalizeProvider),
    checks: healthResponse.checks.map(normalizeProviderHealth),
  };
}

export async function getWorkspaceChatSnapshot(): Promise<readonly WorkspaceConversationSummary[]> {
  if (!resolvedApiBaseUrl()) {
    return [];
  }
  const response = await requestJson<{ conversations: readonly Record<string, unknown>[] }>("/workspace/chat/conversations");
  return response.conversations.map(normalizeConversation);
}

export async function getGovernanceManagementSnapshot(): Promise<{
  documents: readonly GovernanceConfigDocument[];
  versions: readonly GovernanceConfigVersion[];
}> {
  if (!resolvedApiBaseUrl()) {
    return { documents: [], versions: [] };
  }
  const response = await requestJson<{ documents: readonly Record<string, unknown>[] }>("/governance/configs");
  const documents = response.documents.map(normalizeGovernanceDocument);
  const versions = (
    await Promise.all(
      documents.map(async (document) => {
        try {
          const versionResponse = await requestJson<{ versions: readonly Record<string, unknown>[] }>(`/governance/configs/${document.id}/versions`);
          return versionResponse.versions.map(normalizeGovernanceVersion);
        } catch {
          return [];
        }
      }),
    )
  ).flat();
  return { documents, versions };
}

export async function getPromptStudioSnapshot(): Promise<{
  prompts: readonly PromptDocument[];
  versions: readonly PromptVersion[];
  testResult: PromptTestSummary;
}> {
  if (!resolvedApiBaseUrl()) {
    return { prompts: [], versions: [], testResult: emptyDashboardSnapshot().promptStudio.testResult };
  }
  const response = await requestJson<{ prompts: readonly Record<string, unknown>[] }>("/prompt-studio/prompts");
  const prompts = response.prompts.map(normalizePromptDocument);
  const versions = (
    await Promise.all(
      prompts.map(async (prompt) => {
        try {
          const versionResponse = await requestJson<{ versions: readonly Record<string, unknown>[] }>(`/prompt-studio/prompts/${prompt.id}/versions`);
          return versionResponse.versions.map(normalizePromptVersion);
        } catch {
          return [];
        }
      }),
    )
  ).flat();
  return { prompts, versions, testResult: emptyDashboardSnapshot().promptStudio.testResult };
}

function normalizeProvider(item: Record<string, unknown>): LlmProviderSummary {
  return {
    id: String(item.id),
    name: String(item.name),
    kind: String(item.kind) as LlmProviderSummary["kind"],
    baseUrl: item.base_url ? String(item.base_url) : undefined,
    apiKey: item.api_key ? String(item.api_key) : undefined,
    defaultModel: String(item.default_model ?? ""),
    status: String(item.status) as LlmProviderSummary["status"],
    agentModels: (item.agent_models ?? {}) as Record<string, string>,
    contextWindowTokens: item.context_window_tokens ? Number(item.context_window_tokens) : undefined,
    maxOutputTokens: item.max_output_tokens ? Number(item.max_output_tokens) : undefined,
    reservedOutputTokens: item.reserved_output_tokens ? Number(item.reserved_output_tokens) : undefined,
    maxPromptTokens: item.max_prompt_tokens ? Number(item.max_prompt_tokens) : undefined,
    configured: Boolean(item.configured),
    isDefault: Boolean(item.is_default ?? false),
    updatedAt: String(item.updated_at ?? ""),
    metadata: (item.metadata ?? {}) as Record<string, unknown>,
    modelProfiles: normalizeModelProfiles(item.model_profiles),
  };
}

function normalizeProviderHealth(item: Record<string, unknown>): LlmProviderHealthCheck {
  return {
    providerId: String(item.provider_id),
    status: String(item.status) as LlmProviderHealthCheck["status"],
    message: String(item.message),
    checkedAt: String(item.checked_at ?? ""),
  };
}

function normalizeModelProfiles(value: unknown): Record<string, import("./types").LlmModelCapabilityProfile> | undefined {
  if (!value || typeof value !== "object") return undefined;
  const entries = Object.entries(value as Record<string, unknown>);
  const mapped = entries
    .map(([key, raw]) => [key, normalizeModelProfile(raw as Record<string, unknown>)] as const)
    .filter(([, profile]) => Boolean(profile));
  if (!mapped.length) return undefined;
  return Object.fromEntries(mapped);
}

function normalizeModelProfile(item: Record<string, unknown>): import("./types").LlmModelCapabilityProfile {
  return {
    providerId: item.provider_id ? String(item.provider_id) : undefined,
    providerType: String(item.provider_type ?? ""),
    modelId: String(item.model_id ?? ""),
    displayName: item.display_name ? String(item.display_name) : undefined,
    contextWindowTokens: Number(item.context_window_tokens ?? 4096),
    maxInputTokens: Number(item.max_input_tokens ?? 2500),
    maxOutputTokens: Number(item.max_output_tokens ?? 1024),
    supportsStreaming: Boolean(item.supports_streaming ?? true),
    supportsJsonMode: Boolean(item.supports_json_mode ?? false),
    supportsTools: Boolean(item.supports_tools ?? false),
    supportsEmbeddings: Boolean(item.supports_embeddings ?? false),
    recommendedForChat: Boolean(item.recommended_for_chat ?? true),
    recommendedForAgents: Boolean(item.recommended_for_agents ?? true),
    recommendedForCode: Boolean(item.recommended_for_code ?? false),
    compactModeRequired: Boolean(item.compact_mode_required ?? true),
    notes: item.notes ? String(item.notes) : undefined,
    detectionSource: String(item.detection_source ?? "estimated"),
    loadedModelId: item.loaded_model_id ? String(item.loaded_model_id) : undefined,
    localRuntimeManagedByPlatform: Boolean(item.local_runtime_managed_by_platform ?? false),
    runtimeStatus: item.runtime_status ? String(item.runtime_status) : undefined,
    lastLoadedAt: item.last_loaded_at ? String(item.last_loaded_at) : undefined,
    lastHealthCheckAt: item.last_health_check_at ? String(item.last_health_check_at) : undefined,
    lastRefreshedAt: String(item.last_refreshed_at ?? ""),
  };
}

function normalizeConversation(item: Record<string, unknown>): WorkspaceConversationSummary {
  const messages = Array.isArray(item.messages) ? item.messages as Record<string, unknown>[] : [];
  const attachments = Array.isArray(item.attachments) ? item.attachments as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    title: String(item.title),
    updatedAt: String(item.updated_at ?? item.updatedAt ?? ""),
    messages: messages.map((message) => ({
      id: String(message.id),
      role: String(message.role) as WorkspaceConversationSummary["messages"][number]["role"],
      content: String(message.content ?? ""),
      status: message.status ? String(message.status) as WorkspaceConversationSummary["messages"][number]["status"] : undefined,
      error: message.error ? String(message.error) : undefined,
      attachmentIds: Array.isArray(message.attachment_ids) ? message.attachment_ids.map(String) : [],
      workflowId: message.workflow_id ? String(message.workflow_id) : undefined,
      createdAt: String(message.created_at ?? ""),
    })),
    attachments: attachments.map((attachment) => ({
      id: String(attachment.id),
      kind: String(attachment.kind) as WorkspaceConversationSummary["attachments"][number]["kind"],
      name: String(attachment.name),
      uri: attachment.uri ? String(attachment.uri) : undefined,
      path: attachment.path ? String(attachment.path) : undefined,
      sizeBytes: Number(attachment.size_bytes ?? 0),
    })),
  };
}

function normalizeGovernanceDocument(item: Record<string, unknown>): GovernanceConfigDocument {
  return {
    id: String(item.id),
    scope: String(item.scope) as GovernanceConfigDocument["scope"],
    kind: String(item.kind) as GovernanceConfigDocument["kind"],
    name: String(item.name),
    markdown: String(item.markdown ?? ""),
    agentName: item.agent_name ? String(item.agent_name) : undefined,
    version: Number(item.version ?? 1),
    updatedBy: String(item.updated_by ?? "system"),
    updatedAt: String(item.updated_at ?? ""),
    sourceType: item.source_type ? String(item.source_type) : undefined,
    sourcePath: item.source_path ? String(item.source_path) : undefined,
    isActive: Boolean(item.is_active ?? true),
    protected: Boolean(item.protected ?? false),
  };
}

function normalizeGovernanceVersion(item: Record<string, unknown>): GovernanceConfigVersion {
  return {
    id: String(item.id),
    documentId: String(item.document_id),
    version: Number(item.version ?? 1),
    markdown: String(item.markdown ?? ""),
    changedBy: String(item.changed_by ?? "system"),
    changeSummary: item.change_summary ? String(item.change_summary) : undefined,
    createdAt: String(item.created_at ?? ""),
  };
}

function normalizePromptDocument(item: Record<string, unknown>): PromptDocument {
  const variables = Array.isArray(item.variables) ? item.variables as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    name: String(item.name),
    scope: String(item.scope) as PromptDocument["scope"],
    agentName: item.agent_name ? String(item.agent_name) : undefined,
    markdown: String(item.markdown ?? ""),
    variables: variables.map((variable) => ({
      name: String(variable.name),
      description: variable.description ? String(variable.description) : undefined,
      required: Boolean(variable.required),
      default: variable.default ? String(variable.default) : undefined,
    })),
    status: String(item.status) as PromptDocument["status"],
    version: Number(item.version ?? 1),
    updatedBy: String(item.updated_by ?? "system"),
    updatedAt: String(item.updated_at ?? ""),
  };
}

function normalizePromptVersion(item: Record<string, unknown>): PromptVersion {
  const variables = Array.isArray(item.variables) ? item.variables as Record<string, unknown>[] : [];
  return {
    id: String(item.id),
    promptId: String(item.prompt_id),
    version: Number(item.version ?? 1),
    markdown: String(item.markdown ?? ""),
    variables: variables.map((variable) => ({
      name: String(variable.name),
      description: variable.description ? String(variable.description) : undefined,
      required: Boolean(variable.required),
      default: variable.default ? String(variable.default) : undefined,
    })),
    changedBy: String(item.changed_by ?? "system"),
    changeSummary: item.change_summary ? String(item.change_summary) : undefined,
    createdAt: String(item.created_at ?? ""),
  };
}

function emptyDashboardSnapshot(): DashboardSnapshot {
  const now = new Date().toISOString();
  const workflowId = "no-active-workflow";
  const agents = ["ba", "architect", "developer", "qa", "docs", "pr"] as const;
  return {
    workflowId,
    agents: agents.map((key) => ({
      key,
      name: key,
      status: "idle",
      currentTask: "No active execution",
      lastEventAt: now,
      retryCount: 0,
    })),
    stages: agents.map((id) => ({ id, label: id, status: "pending", metadata: {} })),
    events: [],
    timeline: [],
    logs: [],
    qaReport: {
      executionId: workflowId,
      status: "running",
      coveragePercent: 0,
      unitTests: 0,
      integrationTests: 0,
      browserTests: 0,
      bugs: [],
      screenshots: [],
    },
    docs: [],
    pullRequest: {
      id: workflowId,
      title: "No pull request generated",
      status: "draft",
      branch: "",
      target: "",
      changedFiles: 0,
      riskLevel: "info",
      summary: "No active execution has generated PR output.",
    },
    approvals: [],
    observability: {
      workflow: {
        workflowId,
        durationMs: 0,
        agentCount: agents.length,
        retries: 0,
        failures: 0,
        qaRejectionRate: 0,
        tokenUsage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 },
        promptTelemetry: { messageCount: 0, characterCount: 0, estimatedTokens: 0 },
      },
      agents: [],
      metrics: [],
      exporters: {
        opentelemetryReady: false,
        datadogReady: false,
        prometheusReady: false,
        grafanaReady: false,
      },
    },
    governance: { documents: [], versions: [] },
    promptStudio: {
      prompts: [],
      versions: [],
      testResult: {
        preview: { rendered: "", missingVariables: [], estimatedTokens: 0, characterCount: 0 },
        executionPreview: "",
        evaluation: { score: 0, passed: false, findings: [] },
      },
    },
    workspace: { conversations: [], workspaces: [], projects: [], isolation: [] },
    visualization: {
      workflowId,
      status: "pending",
      progressPercent: 0,
      durationMs: 0,
      nodes: agents.map((id) => ({
        id,
        label: id,
        agentName: id,
        status: "pending",
        retryCount: 0,
        metadata: {},
      })),
      edges: [],
      timeline: [],
      mermaid: "flowchart LR",
      metadata: {},
    },
    mermaid: "flowchart LR",
  };
}
