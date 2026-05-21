import { AppShell } from "@/components/layout/app-shell";
import { AgentStatusGrid } from "@/features/agents/agent-status-grid";
import { MetricStrip } from "@/features/dashboard/metric-strip";
import { MermaidDiagram } from "@/features/diagrams/mermaid-diagram";
import { ExecutionTimeline } from "@/features/executions/execution-timeline";
import { LiveLogViewer } from "@/features/executions/live-log-viewer";
import { GeneratedDocsViewer } from "@/features/docs/generated-docs-viewer";
import { PrSummaryPanel } from "@/features/pr/pr-summary-panel";
import { QaReportViewer } from "@/features/qa/qa-report-viewer";
import { WorkflowMap } from "@/features/workflows/workflow-map";
import { getDashboardSnapshot } from "@/lib/api";

export default async function DashboardPage(): Promise<JSX.Element> {
  const snapshot = await getDashboardSnapshot();

  return (
    <AppShell>
      <div className="space-y-6">
        <MetricStrip snapshot={snapshot} />
        <WorkflowMap stages={snapshot.stages} />
        <AgentStatusGrid agents={snapshot.agents} />
        <div className="grid gap-6 xl:grid-cols-[1fr_28rem]">
          <ExecutionTimeline items={snapshot.timeline} />
          <QaReportViewer report={snapshot.qaReport} />
        </div>
        <LiveLogViewer workflowId={snapshot.workflowId} logs={snapshot.logs} events={snapshot.events} />
        <div className="grid gap-6 xl:grid-cols-2">
          <MermaidDiagram chart={snapshot.mermaid} />
          <div className="space-y-6">
            <GeneratedDocsViewer docs={snapshot.docs} />
            <PrSummaryPanel pullRequest={snapshot.pullRequest} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
