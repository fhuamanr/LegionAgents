"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, CircleCheck, CircleDot, CircleX } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  const [filter, setFilter] = useState<"all" | "errors" | "agent" | "workflow" | "provider">("all");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const filteredItems = useMemo(() => {
    if (filter === "all") return items;
    if (filter === "errors") return items.filter((item) => item.status === "failed");
    if (filter === "agent") return items.filter((item) => item.title.toLowerCase().includes("agent"));
    if (filter === "provider") return items.filter((item) => item.title.toLowerCase().includes("provider") || item.description.toLowerCase().includes("provider"));
    return items.filter((item) => item.title.toLowerCase().includes("workflow"));
  }, [items, filter]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filteredItems]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Execution Timeline</CardTitle>
        <CardDescription>Chronological workflow transition history</CardDescription>
        <div className="flex flex-wrap gap-2">
          {(["all", "errors", "agent", "workflow", "provider"] as const).map((value) => (
            <button
              key={value}
              type="button"
              className="rounded-md border px-2 py-1 text-xs"
              onClick={() => setFilter(value)}
            >
              <Badge variant={filter === value ? "default" : "muted"}>{value}</Badge>
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div ref={scrollRef} data-testid="execution-timeline-scroll" className="max-h-[28rem] overflow-y-auto pr-1">
        <ol className="space-y-3">
          {filteredItems.map((item) => {
            const Icon = iconByStatus[item.status];
            return (
              <li key={item.id} className="grid grid-cols-[1.25rem_1fr] gap-2 rounded-md border p-2">
                <Icon className="mt-0.5 h-4 w-4 text-primary" aria-hidden="true" />
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium">{item.title}</div>
                    <time className="text-xs text-muted-foreground">{formatDateTime(item.timestamp)}</time>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
                </div>
              </li>
            );
          })}
        </ol>
        </div>
      </CardContent>
    </Card>
  );
}
