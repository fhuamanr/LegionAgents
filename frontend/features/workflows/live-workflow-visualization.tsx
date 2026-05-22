"use client";

import { Activity, GitBranch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MermaidDiagram } from "@/features/diagrams/mermaid-diagram";
import { ExecutionGraph } from "@/features/workflows/execution-graph";
import { useWorkflowTelemetry } from "@/hooks/use-workflow-telemetry";
import { formatDuration } from "@/lib/utils";
import type { WorkflowTelemetrySnapshot } from "@/lib/types";

export function LiveWorkflowVisualization({
  workflowId,
  snapshot,
}: Readonly<{
  workflowId: string;
  snapshot: WorkflowTelemetrySnapshot;
}>): JSX.Element {
  const telemetry = useWorkflowTelemetry(workflowId, snapshot);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Live Workflow Graph</CardTitle>
              <CardDescription>Execution nodes, dependencies, retries, and QA loops</CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">
                <Activity className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                {Math.round(telemetry.progressPercent)}%
              </Badge>
              <Badge variant="muted">
                <GitBranch className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                {formatDuration(telemetry.durationMs)}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <ExecutionGraph nodes={telemetry.nodes} edges={telemetry.edges} />
        </CardContent>
      </Card>
      <MermaidDiagram chart={telemetry.mermaid} />
    </div>
  );
}
