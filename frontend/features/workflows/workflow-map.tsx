import { ArrowRight, RefreshCcw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { WorkflowStage, WorkflowStageStatus } from "@/lib/types";

const statusVariant: Record<WorkflowStageStatus, "default" | "success" | "warning" | "destructive" | "muted"> = {
  pending: "muted",
  queued: "muted",
  running: "default",
  repairing: "warning",
  completed: "success",
  completed_with_warnings: "warning",
  blocked: "destructive",
  rejected: "warning",
  failed: "destructive",
};

export function WorkflowMap({ stages }: Readonly<{ stages: readonly WorkflowStage[] }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Workflow Visualization</CardTitle>
        <CardDescription>BA to PR delivery path with QA rejection loop support</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-stretch">
          {stages.map((stage, index) => (
            <div key={stage.id} className="flex flex-1 items-center gap-3">
              <div className="min-h-28 flex-1 rounded-md border bg-background p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">{stage.label}</div>
                  <Badge variant={statusVariant[stage.status]}>{stage.status}</Badge>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  {Object.entries(stage.metadata).map(([key, value]) => (
                    <div key={key} className="rounded-md bg-muted px-2 py-1">
                      <span className="capitalize">{key}</span>: {String(value)}
                    </div>
                  ))}
                </div>
              </div>
              {index < stages.length - 1 ? <ArrowRight className="hidden h-4 w-4 shrink-0 text-muted-foreground xl:block" aria-hidden="true" /> : null}
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          <RefreshCcw className="h-4 w-4" aria-hidden="true" />
          QA rejection loops route back to Developer with retry metadata and isolated context.
        </div>
      </CardContent>
    </Card>
  );
}
