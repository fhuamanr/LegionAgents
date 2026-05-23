import { AppShell } from "@/components/layout/app-shell";
import { AgentStatusGrid } from "@/features/agents/agent-status-grid";
import { ApprovalGatesPanel } from "@/features/approvals/approval-gates-panel";
import { MetricStrip } from "@/features/dashboard/metric-strip";
import { MermaidDiagram } from "@/features/diagrams/mermaid-diagram";
import { ExecutionTimeline } from "@/features/executions/execution-timeline";
import { LiveLogViewer } from "@/features/executions/live-log-viewer";
import { ObservabilityPanel } from "@/features/observability/observability-panel";
import { GeneratedDocsViewer } from "@/features/docs/generated-docs-viewer";
import { PrSummaryPanel } from "@/features/pr/pr-summary-panel";
import { QaReportViewer } from "@/features/qa/qa-report-viewer";
import { LiveWorkflowVisualization } from "@/features/workflows/live-workflow-visualization";
import { WorkflowMap } from "@/features/workflows/workflow-map";
import { getDashboardSnapshot, getProviderManagementSnapshot } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { ServerCog, TriangleAlert } from "lucide-react";

export default async function DashboardPage(): Promise<JSX.Element> {
  const [snapshot, providers] = await Promise.all([getDashboardSnapshot(), getProviderManagementSnapshot()]);
  const providerReady = providers.checks.some((check) => check.status === "ok");

  return (
    <AppShell>
      <div className="space-y-6">
        {!providerReady ? <ProviderSetupBanner /> : null}
        <MetricStrip snapshot={snapshot} />
        <LiveWorkflowVisualization workflowId={snapshot.workflowId} snapshot={snapshot.visualization} />
        <WorkflowMap stages={snapshot.stages} />
        <AgentStatusGrid agents={snapshot.agents} />
        <ApprovalGatesPanel approvals={snapshot.approvals} />
        <ObservabilityPanel observability={snapshot.observability} />
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

function ProviderSetupBanner(): JSX.Element {
  return (
    <Card className="border-amber-500/40 bg-amber-500/10">
      <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex min-w-0 items-start gap-3">
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />
          <div>
            <div className="text-sm font-semibold">Configure an AI provider before running real workflows</div>
            <p className="mt-1 text-xs text-muted-foreground">OpenAI/Codex, OpenRouter, Ollama, LM Studio, or a custom OpenAI-compatible endpoint is required for agent execution.</p>
          </div>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/dashboard/providers" className="gap-2">
            <ServerCog className="h-4 w-4" aria-hidden="true" />
            Providers
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}
