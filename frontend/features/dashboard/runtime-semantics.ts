import type { ExecutionEvent, WorkflowTelemetryTimelineItem } from "@/lib/types";

export type AggregatedTimelineItem = {
  id: string;
  title: string;
  description: string;
  timestamp: string;
  severity: "info" | "warning" | "high";
  kind: "agent" | "workflow" | "provider" | "governance" | "artifacts" | "other";
};

export function aggregateExecutionEvents(events: readonly ExecutionEvent[]): readonly AggregatedTimelineItem[] {
  const groupedToken = new Map<string, { agent: string; count: number; startedAt: string; endedAt: string }>();
  const groupedProgress = new Map<string, { agent: string; count: number; startedAt: string; endedAt: string }>();
  const groupedArtifacts = new Map<string, { agent: string; count: number; startedAt: string; endedAt: string }>();
  const groupedRetries = new Map<string, { agent: string; count: number; startedAt: string; endedAt: string }>();
  const result: AggregatedTimelineItem[] = [];

  for (const event of events) {
    if (event.type === "token_streamed") {
      const key = `${event.agent}`;
      const prev = groupedToken.get(key);
      const tokenCount = String(event.message ?? "").length;
      if (!prev) {
        groupedToken.set(key, { agent: event.agent, count: tokenCount, startedAt: event.timestamp, endedAt: event.timestamp });
      } else {
        prev.count += tokenCount;
        prev.endedAt = event.timestamp;
      }
      continue;
    }
    if (event.type === "progress_updated" || event.type === "log_emitted") {
      const key = `${event.agent}`;
      const prev = groupedProgress.get(key);
      if (!prev) {
        groupedProgress.set(key, { agent: event.agent, count: 1, startedAt: event.timestamp, endedAt: event.timestamp });
      } else {
        prev.count += 1;
        prev.endedAt = event.timestamp;
      }
      continue;
    }
    if (event.type === "output_generated" && typeof event.payload.artifact_count === "number") {
      const key = `${event.agent}`;
      const prev = groupedArtifacts.get(key);
      const count = Number(event.payload.artifact_count ?? 0);
      if (!prev) {
        groupedArtifacts.set(key, { agent: event.agent, count, startedAt: event.timestamp, endedAt: event.timestamp });
      } else {
        prev.count += count;
        prev.endedAt = event.timestamp;
      }
      continue;
    }
    if (event.type === "retry_started") {
      const key = `${event.agent}`;
      const prev = groupedRetries.get(key);
      if (!prev) {
        groupedRetries.set(key, { agent: event.agent, count: 1, startedAt: event.timestamp, endedAt: event.timestamp });
      } else {
        prev.count += 1;
        prev.endedAt = event.timestamp;
      }
      continue;
    }
    if (event.type === "telemetry_recorded") {
      const telemetryEvent = String(event.payload.event ?? "").trim().toLowerCase();
      if (["continuation_mode_started", "qa_feedback_generated", "governance_repaired", "provider_selected_per_agent", "stage_transition"].includes(telemetryEvent)) {
        result.push({
          id: event.id,
          title: humanizeEvent(telemetryEvent),
          description: event.message || "Runtime telemetry event.",
          timestamp: event.timestamp,
          severity: telemetryEvent.includes("governance") ? "warning" : "info",
          kind: classifyEventKind(telemetryEvent, event.message),
        });
      }
      continue;
    }
    result.push({
      id: event.id,
      title: humanizeEvent(event.type),
      description: event.message || "Runtime event recorded.",
      timestamp: event.timestamp,
      severity: event.severity === "critical" || event.severity === "high" ? "high" : event.severity === "medium" ? "warning" : "info",
      kind: classifyEventKind(event.type, event.message),
    });
  }

  for (const [key, entry] of groupedToken.entries()) {
    result.push({
      id: `token-aggregate-${key}-${entry.endedAt}`,
      title: `${entry.agent} streamed tokens`,
      description: `${entry.count.toLocaleString()} token characters streamed during execution window.`,
      timestamp: entry.endedAt,
      severity: "info",
      kind: "provider",
    });
  }
  for (const [key, entry] of groupedArtifacts.entries()) {
    result.push({
      id: `artifact-aggregate-${key}-${entry.endedAt}`,
      title: `${entry.agent} persisted artifacts`,
      description: `${entry.count.toLocaleString()} artifacts persisted across execution events.`,
      timestamp: entry.endedAt,
      severity: "info",
      kind: "artifacts",
    });
  }
  for (const [key, entry] of groupedRetries.entries()) {
    result.push({
      id: `retry-aggregate-${key}-${entry.endedAt}`,
      title: `${entry.agent} retries`,
      description: `${entry.count.toLocaleString()} retries triggered.`,
      timestamp: entry.endedAt,
      severity: entry.count > 2 ? "warning" : "info",
      kind: "agent",
    });
  }
  for (const [key, entry] of groupedProgress.entries()) {
    result.push({
      id: `progress-aggregate-${key}-${entry.endedAt}`,
      title: `${entry.agent} low-level runtime events`,
      description: `${entry.count.toLocaleString()} progress/log events collapsed.`,
      timestamp: entry.endedAt,
      severity: "info",
      kind: "other",
    });
  }

  return result.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

export function aggregateTelemetryTimeline(items: readonly WorkflowTelemetryTimelineItem[]): readonly AggregatedTimelineItem[] {
  return items.map((item) => ({
    id: item.id,
    title: humanizeEvent(item.eventType),
    description: item.message || "Telemetry event.",
    timestamp: item.timestamp,
    severity: item.eventType.includes("failed") ? "high" : item.eventType.includes("warning") || item.eventType.includes("repair") ? "warning" : "info",
    kind: classifyEventKind(item.eventType, item.message),
  }));
}

function humanizeEvent(eventType: string): string {
  const mapped: Record<string, string> = {
    agent_started: "Agent started",
    agent_completed: "Agent completed",
    agent_failed: "Agent failed",
    retry_started: "Retry started",
    QA_failed: "QA failed",
    PR_generated: "PR generated",
    docs_generated: "Docs generated",
    output_generated: "Output generated",
    telemetry_recorded: "Telemetry recorded",
    governance_warning_detected: "Governance warning",
    governance_repair_applied: "Governance repaired",
    continuation_mode_started: "Continuation mode started",
    qa_feedback_generated: "QA feedback generated",
    governance_repaired: "Governance repaired",
    provider_selected_per_agent: "Provider selected",
    stage_transition: "Stage transition",
  };
  return mapped[eventType] ?? eventType.replaceAll("_", " ");
}

function classifyEventKind(eventType: string, message: string): AggregatedTimelineItem["kind"] {
  const value = `${eventType} ${message}`.toLowerCase();
  if (value.includes("governance")) return "governance";
  if (value.includes("artifact")) return "artifacts";
  if (value.includes("provider") || value.includes("model") || value.includes("token")) return "provider";
  if (value.includes("workflow")) return "workflow";
  if (value.includes("agent") || value.includes("retry") || value.includes("pass")) return "agent";
  return "other";
}
