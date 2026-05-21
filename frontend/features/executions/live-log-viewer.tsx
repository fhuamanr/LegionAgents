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
            {logs.map((log) => (
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
      </CardContent>
    </Card>
  );
}
