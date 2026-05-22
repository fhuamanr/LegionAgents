import type { AgentKey, ExecutionEvent, WorkflowTelemetrySnapshot } from "./types";

export interface ExecutionStream {
  close: () => void;
}

export function connectExecutionStream(
  workflowId: string,
  onEvent: (event: ExecutionEvent) => void,
  onError?: (error: Event) => void,
): ExecutionStream | null {
  const wsBaseUrl = process.env.NEXT_PUBLIC_WS_BASE_URL;

  if (!wsBaseUrl || typeof window === "undefined") {
    return null;
  }

  const socket = new WebSocket(`${wsBaseUrl}/ws/executions/${workflowId}`);

  socket.addEventListener("message", (message) => {
    onEvent(normalizeExecutionEvent(JSON.parse(message.data as string) as Record<string, unknown>));
  });

  if (onError) {
    socket.addEventListener("error", onError);
  }

  return {
    close: () => socket.close(),
  };
}

export interface WorkflowTelemetryStream {
  close: () => void;
}

export function connectWorkflowTelemetryStream(
  workflowId: string,
  onTelemetry: (snapshot: WorkflowTelemetrySnapshot) => void,
  onError?: (error: Event) => void,
): WorkflowTelemetryStream | null {
  const wsBaseUrl = process.env.NEXT_PUBLIC_WS_BASE_URL;

  if (!wsBaseUrl || typeof window === "undefined") {
    return null;
  }

  const socket = new WebSocket(`${wsBaseUrl}/ws/workflows/${workflowId}/telemetry`);

  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data as string) as { telemetry?: Record<string, unknown> };
    if (payload.telemetry) {
      onTelemetry(normalizeWorkflowTelemetry(payload.telemetry));
    }
  });

  if (onError) {
    socket.addEventListener("error", onError);
  }

  return {
    close: () => socket.close(),
  };
}

export function normalizeWorkflowTelemetry(payload: Record<string, unknown>): WorkflowTelemetrySnapshot {
  return {
    workflowId: String(payload.workflowId ?? payload.workflow_id ?? ""),
    status: String(payload.status ?? "pending") as WorkflowTelemetrySnapshot["status"],
    activeAgent: optionalAgent(payload.activeAgent ?? payload.active_agent),
    progressPercent: Number(payload.progressPercent ?? payload.progress_percent ?? 0),
    durationMs: Number(payload.durationMs ?? payload.duration_ms ?? 0),
    nodes: asArray(payload.nodes).map((node) => ({
      id: String(node.id ?? "ba") as AgentKey,
      label: String(node.label ?? node.id ?? ""),
      agentName: String(node.agentName ?? node.agent_name ?? node.id ?? "ba") as AgentKey,
      status: String(node.status ?? "pending") as WorkflowTelemetrySnapshot["nodes"][number]["status"],
      startedAt: optionalString(node.startedAt ?? node.started_at),
      completedAt: optionalString(node.completedAt ?? node.completed_at),
      durationMs: optionalNumber(node.durationMs ?? node.duration_ms),
      retryCount: Number(node.retryCount ?? node.retry_count ?? 0),
      metadata: asMetadata(node.metadata),
    })),
    edges: asArray(payload.edges).map((edge) => ({
      source: String(edge.source ?? "ba") as AgentKey,
      target: String(edge.target ?? "architect") as AgentKey,
      label: optionalString(edge.label),
      condition: optionalString(edge.condition),
      isLoop: Boolean(edge.isLoop ?? edge.is_loop ?? false),
      metadata: asMetadata(edge.metadata),
    })),
    timeline: asArray(payload.timeline).map((item) => ({
      id: String(item.id ?? `telemetry-${Date.now()}`),
      eventType: String(item.eventType ?? item.event_type ?? ""),
      agentName: optionalAgent(item.agentName ?? item.agent_name),
      message: String(item.message ?? ""),
      timestamp: String(item.timestamp ?? new Date().toISOString()),
      durationMs: optionalNumber(item.durationMs ?? item.duration_ms),
      metadata: asMetadata(item.metadata),
    })),
    mermaid: String(payload.mermaid ?? "flowchart LR"),
    metadata: asMetadata(payload.metadata),
  };
}

function normalizeExecutionEvent(payload: Record<string, unknown>): ExecutionEvent {
  const type = String(payload.type ?? "log_emitted") as ExecutionEvent["type"];
  const agent = String(payload.agent ?? payload.agent_name ?? "ba") as AgentKey;
  return {
    id: String(payload.id ?? `event-${Date.now()}`),
    type: isKnownEventType(type) ? type : "agent_started",
    agent,
    message: String(payload.message ?? ""),
    timestamp: String(payload.timestamp ?? new Date().toISOString()),
    severity: type === "agent_failed" || type === "QA_failed" ? "high" : type === "retry_started" ? "medium" : "info",
  };
}

function optionalAgent(value: unknown): AgentKey | undefined {
  return typeof value === "string" && value.length > 0 ? (value as AgentKey) : undefined;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

function asMetadata(value: unknown): Record<string, string | number | boolean> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, string | number | boolean] =>
      ["string", "number", "boolean"].includes(typeof entry[1]),
    ),
  );
}

function isKnownEventType(type: string): type is ExecutionEvent["type"] {
  return ["agent_started", "agent_completed", "agent_failed", "retry_started", "QA_failed", "PR_generated", "docs_generated"].includes(type);
}
