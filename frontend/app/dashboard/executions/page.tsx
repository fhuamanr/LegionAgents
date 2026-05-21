import { AppShell } from "@/components/layout/app-shell";
import { ExecutionTimeline } from "@/features/executions/execution-timeline";
import { LiveLogViewer } from "@/features/executions/live-log-viewer";
import { WorkflowMap } from "@/features/workflows/workflow-map";
import { getDashboardSnapshot } from "@/lib/api";

export default async function ExecutionsPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="space-y-6">
        <WorkflowMap stages={snapshot.stages} />
        <ExecutionTimeline items={snapshot.timeline} />
        <LiveLogViewer workflowId={snapshot.workflowId} logs={snapshot.logs} events={snapshot.events} />
      </div>
    </AppShell>
  );
}
