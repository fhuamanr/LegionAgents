import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DashboardSnapshot } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

export function ExecutionSummaryHeader({ snapshot }: Readonly<{ snapshot: DashboardSnapshot }>): JSX.Element {
  const warningsRepaired = snapshot.events.filter((event) => event.message.toLowerCase().includes("repaired")).length;
  const artifacts = snapshot.events
    .filter((event) => event.type === "output_generated")
    .reduce((total, event) => total + Number(event.payload.artifact_count ?? 0), 0);
  const depthScore = extractDepthScore(snapshot);
  const mode = String(snapshot.visualization.metadata.execution_mode ?? snapshot.visualization.metadata.workflow_mode ?? "not available");
  const provider = String(snapshot.visualization.metadata.provider_model ?? "not available");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Execution Summary</CardTitle>
        <CardDescription>Operational snapshot for long-running orchestration workflows</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
        <SummaryCell label="Workflow" value={snapshot.workflowId} />
        <SummaryCell label="Status" value={snapshot.visualization.status} badge />
        <SummaryCell label="Duration" value={formatDuration(snapshot.visualization.durationMs)} />
        <SummaryCell label="Agents" value={`${snapshot.visualization.nodes.filter((n) => n.status !== "pending").length}/${snapshot.visualization.nodes.length}`} />
        <SummaryCell label="Artifacts" value={String(artifacts)} />
        <SummaryCell label="Warnings repaired" value={String(warningsRepaired)} />
        <SummaryCell label="Depth score" value={depthScore} />
        <SummaryCell label="Mode" value={mode} />
        <SummaryCell label="Provider" value={provider} className="md:col-span-2 xl:col-span-4" />
      </CardContent>
    </Card>
  );
}

function SummaryCell({
  label,
  value,
  badge = false,
  className = "",
}: Readonly<{ label: string; value: string; badge?: boolean; className?: string }>): JSX.Element {
  return (
    <div className={`rounded-md border bg-background p-3 ${className}`}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 text-sm font-semibold">
        {badge ? <Badge variant="muted">{value}</Badge> : value}
      </div>
    </div>
  );
}

function extractDepthScore(snapshot: DashboardSnapshot): string {
  const metric = snapshot.observability.metrics.find((item) => item.toLowerCase().includes("depth"));
  return metric ?? "not available";
}
