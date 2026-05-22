import { AppShell } from "@/components/layout/app-shell";
import { LiveLogViewer } from "@/features/executions/live-log-viewer";
import { ObservabilityPanel } from "@/features/observability/observability-panel";
import { getDashboardSnapshot } from "@/lib/api";

export default async function ObservabilityPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="space-y-6">
        <ObservabilityPanel observability={snapshot.observability} />
        <LiveLogViewer workflowId={snapshot.workflowId} logs={snapshot.logs} events={snapshot.events} />
      </div>
    </AppShell>
  );
}
