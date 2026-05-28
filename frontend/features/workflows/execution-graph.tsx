import { AlertTriangle, CheckCircle2, Circle, CircleAlert, CircleDot, Clock3, RefreshCcw, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatDuration } from "@/lib/utils";
import type { WorkflowTelemetryEdge, WorkflowTelemetryNode } from "@/lib/types";

const statusStyles: Record<WorkflowTelemetryNode["status"], string> = {
  pending: "border-border bg-background text-muted-foreground",
  queued: "border-border bg-background text-muted-foreground",
  waiting_for_upstream: "border-border bg-background text-muted-foreground",
  running: "border-primary/60 bg-primary/10 text-foreground",
  validating: "border-sky-500/60 bg-sky-500/10 text-sky-100",
  repairing: "border-amber-500/50 bg-amber-500/10 text-amber-100",
  paused: "border-amber-500/50 bg-amber-500/10 text-amber-100",
  completed: "border-emerald-500/50 bg-emerald-500/10 text-emerald-100",
  completed_with_warnings: "border-amber-500/50 bg-amber-500/10 text-amber-100",
  blocked: "border-red-500/60 bg-red-500/10 text-red-100",
  failed: "border-red-500/60 bg-red-500/10 text-red-100",
};

const statusIcons = {
  pending: Circle,
  queued: Circle,
  waiting_for_upstream: Clock3,
  running: CircleDot,
  validating: CircleDot,
  repairing: RefreshCcw,
  paused: Clock3,
  completed: CheckCircle2,
  completed_with_warnings: CircleAlert,
  blocked: CircleAlert,
  failed: XCircle,
};

export function ExecutionGraph({
  nodes,
  edges,
}: Readonly<{
  nodes: readonly WorkflowTelemetryNode[];
  edges: readonly WorkflowTelemetryEdge[];
}>): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-6">
        {nodes.map((node) => {
          const Icon = statusIcons[node.status];
          return (
            <div key={node.id} className={cn("min-h-36 rounded-md border p-4", statusStyles[node.status])}>
              <div className="flex items-center justify-between gap-2">
                <Icon className="h-4 w-4" aria-hidden="true" />
                <Badge
                  variant={
                    node.status === "failed" || node.status === "blocked"
                      ? "destructive"
                      : node.status === "completed"
                        ? "success"
                        : node.status === "completed_with_warnings" || node.status === "repairing"
                          ? "warning"
                          : node.status === "running" || node.status === "validating"
                            ? "default"
                            : "muted"
                  }
                >
                  {node.status}
                </Badge>
              </div>
              <div className="mt-4 text-sm font-semibold">{node.label}</div>
              <div className="mt-2 text-xs text-muted-foreground">
                {typeof node.durationMs === "number" ? formatDuration(node.durationMs) : "waiting"}
              </div>
              <div className="mt-2 space-y-1 text-[11px] text-muted-foreground">
                <div>artifacts: {Number(node.metadata.artifact_count ?? 0)}</div>
                <div>warnings: {Number(node.metadata.governance_warning_count ?? 0)}</div>
                <div>provider: {String(node.metadata.provider ?? "n/a")}</div>
                <div>model: {String(node.metadata.model ?? "n/a")}</div>
                <div>pass: {String(node.metadata.pass ?? "n/a")}</div>
                {String(node.metadata.continuation_mode ?? "none") !== "none" ? (
                  <div>mode: {String(node.metadata.continuation_mode)}</div>
                ) : null}
              </div>
              {node.retryCount > 0 ? (
                <div className="mt-3 flex items-center gap-1 text-xs text-amber-200">
                  <RefreshCcw className="h-3.5 w-3.5" aria-hidden="true" />
                  {node.retryCount} retries
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {edges.map((edge) => (
          <div key={`${edge.source}-${edge.target}-${edge.condition ?? "direct"}`} className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-xs">
            <span className="font-medium uppercase text-muted-foreground">{edge.source}</span>
            <span className={cn("mx-2 h-px flex-1 bg-border", edge.isLoop ? "bg-amber-400" : "bg-primary/50")} />
            <span className="font-medium uppercase text-muted-foreground">{edge.target}</span>
            {edge.label ? <Badge variant="muted" className="ml-2">{edge.label}</Badge> : null}
            {edge.isLoop ? <AlertTriangle className="ml-2 h-3.5 w-3.5 text-amber-300" aria-hidden="true" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
