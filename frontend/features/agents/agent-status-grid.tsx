import { CircleAlert, CircleCheck, CircleDashed, CircleDot, CircleX } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { AgentStatus, AgentSummary } from "@/lib/types";

const statusIcon: Record<AgentStatus, typeof CircleDot> = {
  idle: CircleDashed,
  running: CircleDot,
  blocked: CircleAlert,
  completed: CircleCheck,
  failed: CircleX,
};

export function AgentStatusGrid({ agents }: Readonly<{ agents: readonly AgentSummary[] }>): JSX.Element {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Agent Status</h2>
        <span className="text-xs text-muted-foreground">{agents.length} isolated runtimes</span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => {
          const Icon = statusIcon[agent.status];
          return (
            <Card key={agent.key}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{agent.name}</CardTitle>
                    <CardDescription>{agent.currentTask}</CardDescription>
                  </div>
                  <Badge variant={agent.status === "failed" ? "destructive" : agent.status === "completed" ? "success" : "default"}>
                    <Icon className="mr-1 h-3 w-3" aria-hidden="true" />
                    {agent.status}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <div className="text-muted-foreground">Last event</div>
                  <div className="mt-1 font-medium">{formatDateTime(agent.lastEventAt)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Retries</div>
                  <div className="mt-1 font-medium">{agent.retryCount}</div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
