import { AppShell } from "@/components/layout/app-shell";
import { ExecutionTimeline } from "@/features/executions/execution-timeline";
import { LiveLogViewer } from "@/features/executions/live-log-viewer";
import { WorkflowArtifactsPanel } from "@/features/executions/workflow-artifacts-panel";
import { LiveWorkflowVisualization } from "@/features/workflows/live-workflow-visualization";
import { getDashboardSnapshot, getWorkflowArtifacts } from "@/lib/api";

export default async function ExecutionsPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();
  const artifacts = await getWorkflowArtifacts(snapshot.workflowId);

  return (
    <AppShell>
      <div className="space-y-6">
        <LiveWorkflowVisualization workflowId={snapshot.workflowId} snapshot={snapshot.visualization} />
        <WorkflowArtifactsPanel workflowId={snapshot.workflowId} artifacts={artifacts} />
        <ExecutionTimeline items={snapshot.timeline} />
        <LiveLogViewer workflowId={snapshot.workflowId} logs={snapshot.logs} events={snapshot.events} />
      </div>
    </AppShell>
  );
}
