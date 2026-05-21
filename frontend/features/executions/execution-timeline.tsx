import { Circle, CircleCheck, CircleDot, CircleX } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDateTime } from "@/lib/utils";
import type { TimelineItem, WorkflowStageStatus } from "@/lib/types";

const iconByStatus: Record<WorkflowStageStatus, typeof Circle> = {
  pending: Circle,
  running: CircleDot,
  completed: CircleCheck,
  rejected: CircleX,
  failed: CircleX,
};

export function ExecutionTimeline({ items }: Readonly<{ items: readonly TimelineItem[] }>): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Execution Timeline</CardTitle>
        <CardDescription>Chronological workflow transition history</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="space-y-4">
          {items.map((item) => {
            const Icon = iconByStatus[item.status];
            return (
              <li key={item.id} className="grid grid-cols-[1.25rem_1fr] gap-3">
                <Icon className="mt-0.5 h-4 w-4 text-primary" aria-hidden="true" />
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium">{item.title}</div>
                    <time className="text-xs text-muted-foreground">{formatDateTime(item.timestamp)}</time>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
