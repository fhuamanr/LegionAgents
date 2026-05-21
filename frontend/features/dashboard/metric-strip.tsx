import { Activity, CheckCircle2, Clock, ShieldCheck } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { DashboardSnapshot } from "@/lib/types";

export function MetricStrip({ snapshot }: Readonly<{ snapshot: DashboardSnapshot }>): JSX.Element {
  const completed = snapshot.stages.filter((stage) => stage.status === "completed").length;
  const running = snapshot.agents.filter((agent) => agent.status === "running").length;
  const retries = snapshot.agents.reduce((total, agent) => total + agent.retryCount, 0);

  const metrics = [
    { label: "Workflow", value: snapshot.workflowId, icon: Activity },
    { label: "Stages complete", value: `${completed}/${snapshot.stages.length}`, icon: CheckCircle2 },
    { label: "Active agents", value: String(running), icon: Clock },
    { label: "Retry count", value: String(retries), icon: ShieldCheck },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardContent className="flex items-center justify-between p-4">
            <div>
              <div className="text-xs text-muted-foreground">{metric.label}</div>
              <div className="mt-1 truncate text-lg font-semibold">{metric.value}</div>
            </div>
            <metric.icon className="h-5 w-5 text-primary" aria-hidden="true" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
