"use client";

import { TerminalSquare } from "lucide-react";
import { useExecutionStream } from "@/hooks/use-execution-stream";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { ExecutionEvent, LogEntry } from "@/lib/types";

export function LiveLogViewer({
  workflowId,
  logs,
  events,
}: Readonly<{
  workflowId: string;
  logs: readonly LogEntry[];
  events: readonly ExecutionEvent[];
}>): JSX.Element {
  const streamEvents = useExecutionStream(workflowId, events);
  const liveLogs = streamEvents
    .filter((event) => event.type === "log_emitted")
    .map((event) => ({
      id: event.id,
      timestamp: event.timestamp,
      level: String(event.payload.level ?? "info") as LogEntry["level"],
      source: String(event.payload.source ?? event.agent),
      message: event.message,
    }));
  const displayedLogs = liveLogs.length > 0 ? liveLogs : logs;
  const tokenEvents = streamEvents.filter((event) => event.type === "token_streamed");
  const outputEvents = streamEvents.filter((event) => event.type === "output_generated" || event.type === "telemetry_recorded");

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Live Logs</CardTitle>
            <CardDescription>Structured runtime logs and execution events</CardDescription>
          </div>
          <Badge variant="success">stream-ready</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="h-80 overflow-auto rounded-md border bg-background p-3 font-mono text-xs">
            {displayedLogs.map((log) => (
              <div key={log.id} className="grid grid-cols-[5.5rem_4.5rem_1fr] gap-2 border-b border-border/70 py-2 last:border-b-0">
                <span className="text-muted-foreground">{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className={log.level === "error" ? "text-red-300" : log.level === "warning" ? "text-amber-300" : "text-primary"}>
                  {log.level}
                </span>
                <span>
                  <span className="text-muted-foreground">{log.source}</span> {log.message}
                </span>
              </div>
            ))}
          </div>
          <div className="h-80 overflow-auto rounded-md border bg-background p-3">
            {streamEvents.map((event) => (
              <div key={event.id} className="mb-3 flex gap-3 rounded-md bg-muted/60 p-3 last:mb-0">
                <TerminalSquare className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{event.type}</span>
                    <Badge variant={event.severity === "high" || event.severity === "critical" ? "destructive" : "muted"}>{event.agent}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{event.message}</p>
                  <div className="mt-2 text-xs text-muted-foreground">{formatDateTime(event.timestamp)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div className="h-56 overflow-auto rounded-md border bg-background p-3">
            <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">Token stream</div>
            <pre className="whitespace-pre-wrap font-mono text-xs text-muted-foreground">
              {tokenEvents.map((event) => event.message).join("") || "Waiting for model tokens from the execution websocket."}
            </pre>
          </div>
          <div className="h-56 overflow-auto rounded-md border bg-background p-3">
            <div className="mb-2 text-xs font-medium uppercase text-muted-foreground">Generated outputs and QA</div>
            {outputEvents.length > 0 ? (
              outputEvents.map((event) => (
                <div key={event.id} className="mb-3 rounded-md bg-muted/60 p-3 last:mb-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={event.type === "telemetry_recorded" ? "success" : "muted"}>{event.agent}</Badge>
                    <span className="text-sm font-medium">{event.message}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{outputSummary(event)}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">Waiting for agent outputs from the execution websocket.</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function outputSummary(event: ExecutionEvent): string {
  if (typeof event.payload.summary === "string" && event.payload.summary.length > 0) {
    return event.payload.summary;
  }
  if (event.payload.qa && typeof event.payload.qa === "object") {
    const qa = event.payload.qa as Record<string, unknown>;
    return `passed=${String(qa.passed)} ${String(qa.summary ?? "")}`.trim();
  }
  if (typeof event.payload.artifact_count === "number") {
    return `${event.payload.artifact_count} artifacts`;
  }
  return "Output metadata recorded.";
}
