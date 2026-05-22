import { AlertTriangle, CheckCircle2, Circle, CircleDot, Clock3, RefreshCcw, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatDuration } from "@/lib/utils";
import type { WorkflowTelemetryEdge, WorkflowTelemetryNode } from "@/lib/types";

const statusStyles: Record<WorkflowTelemetryNode["status"], string> = {
  pending: "border-border bg-background text-muted-foreground",
  running: "border-primary/60 bg-primary/10 text-foreground",
  paused: "border-amber-500/50 bg-amber-500/10 text-amber-100",
  completed: "border-emerald-500/50 bg-emerald-500/10 text-emerald-100",
  failed: "border-red-500/60 bg-red-500/10 text-red-100",
};

const statusIcons = {
  pending: Circle,
  running: CircleDot,
  paused: Clock3,
  completed: CheckCircle2,
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
                <Badge variant={node.status === "failed" ? "destructive" : node.status === "completed" ? "success" : node.status === "running" ? "default" : "muted"}>
                  {node.status}
                </Badge>
              </div>
              <div className="mt-4 text-sm font-semibold">{node.label}</div>
              <div className="mt-2 text-xs text-muted-foreground">
                {typeof node.durationMs === "number" ? formatDuration(node.durationMs) : "waiting"}
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
            {edge.isLoop ? <AlertTriangle className="ml-2 h-3.5 w-3.5 text-amber-300" aria-hidden="true" /> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
