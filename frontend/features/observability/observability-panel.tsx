import type { ReactNode } from "react";
import { Activity, BarChart3, Gauge, RadioTower } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDuration } from "@/lib/utils";
import type { ObservabilitySummary } from "@/lib/types";

export function ObservabilityPanel({ observability }: Readonly<{ observability: ObservabilitySummary }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>Observability</CardTitle>
            <CardDescription>Metrics, tracing, analytics, errors, token usage, and prompt sizes</CardDescription>
          </div>
          <Badge variant="success">OpenTelemetry-ready</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-4">
          <Metric label="Workflow duration" value={formatDuration(observability.workflow.durationMs)} />
          <Metric label="Retries" value={String(observability.workflow.retries)} />
          <Metric label="Failures" value={String(observability.workflow.failures)} />
          <Metric label="QA rejection rate" value={`${Math.round(observability.workflow.qaRejectionRate * 100)}%`} />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Metric label="Token usage" value={observability.workflow.tokenUsage.totalTokens.toLocaleString()} icon={<Gauge className="h-4 w-4" />} />
          <Metric label="Prompt estimate" value={observability.workflow.promptTelemetry.estimatedTokens.toLocaleString()} icon={<BarChart3 className="h-4 w-4" />} />
        </div>
        <div className="mt-5 space-y-3">
          {observability.agents.map((agent) => (
            <div key={agent.agentName} className="rounded-md border bg-background p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Activity className="h-4 w-4 text-primary" aria-hidden="true" />
                  {agent.agentName}
                </div>
                <Badge variant={agent.failures ? "destructive" : "muted"}>{formatDuration(agent.averageExecutionTimeMs)}</Badge>
              </div>
              <div className="mt-3 grid gap-2 text-xs sm:grid-cols-4">
                <span>started {agent.executionsStarted}</span>
                <span>completed {agent.executionsCompleted}</span>
                <span>retries {agent.retries}</span>
                <span>tokens {agent.tokenUsage.totalTokens.toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {observability.metrics.map((metric) => (
            <Badge key={metric} variant="default">
              <RadioTower className="mr-1 h-3 w-3" aria-hidden="true" />
              {metric}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  icon,
}: Readonly<{
  label: string;
  value: string;
  icon?: ReactNode;
}>): JSX.Element {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
    </div>
  );
}
