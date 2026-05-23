import { normalizeWorkflowTelemetry } from "./realtime";
import type { DashboardSnapshot, LlmProviderHealthCheck, LlmProviderSummary, WorkflowTelemetrySnapshot } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

async function requestJson<T>(path: string): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
    next: { revalidate: 10 },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  if (!apiBaseUrl) {
    return emptyDashboardSnapshot();
  }

  try {
    return await requestJson<DashboardSnapshot>("/dashboard/snapshot");
  } catch {
    return emptyDashboardSnapshot();
  }
}

export async function getWorkflowTelemetry(workflowId: string): Promise<WorkflowTelemetrySnapshot> {
  if (!apiBaseUrl) {
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
  if (!apiBaseUrl) {
    return { providers: [], checks: [] };
  }

  try {
    const [providersResponse, healthResponse] = await Promise.all([
      requestJson<{ providers: readonly Record<string, unknown>[] }>("/providers"),
      requestJson<{ checks: readonly Record<string, unknown>[] }>("/providers/health"),
    ]);
    return {
      providers: providersResponse.providers.map(normalizeProvider),
      checks: healthResponse.checks.map(normalizeProviderHealth),
    };
  } catch {
    return { providers: [], checks: [] };
  }
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
    configured: Boolean(item.configured),
    updatedAt: String(item.updated_at ?? ""),
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
