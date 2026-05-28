"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, CircleAlert, CircleDot } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";
import type { TimelineItem } from "@/lib/types";
import { aggregateExecutionEvents, type AggregatedTimelineItem } from "@/features/dashboard/runtime-semantics";

export function ExecutionTimeline({
  items,
  events = [],
}: Readonly<{ items: readonly TimelineItem[]; events?: readonly import("@/lib/types").ExecutionEvent[] }>): JSX.Element {
  const [filter, setFilter] = useState<"all" | "errors" | "agent" | "workflow" | "provider">("all");
  const [query, setQuery] = useState("");
  const [compact, setCompact] = useState(true);
  const [showRaw, setShowRaw] = useState(false);
  const [liveMode, setLiveMode] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const key = "dashboard.timeline.preferences.v1";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(key);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as {
        filter?: "all" | "errors" | "agent" | "workflow" | "provider";
        compact?: boolean;
        showRaw?: boolean;
        liveMode?: boolean;
      };
      if (parsed.filter) setFilter(parsed.filter);
      if (typeof parsed.compact === "boolean") setCompact(parsed.compact);
      if (typeof parsed.showRaw === "boolean") setShowRaw(parsed.showRaw);
      if (typeof parsed.liveMode === "boolean") setLiveMode(parsed.liveMode);
    } catch {
      // ignore invalid local cache
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(key, JSON.stringify({ filter, compact, showRaw, liveMode }));
  }, [filter, compact, showRaw, liveMode]);
  const merged = useMemo<readonly AggregatedTimelineItem[]>(() => {
    const fromItems: AggregatedTimelineItem[] = items.map((item) => ({
      id: item.id,
      title: item.title,
      description: item.description,
      timestamp: item.timestamp,
      severity: item.status === "failed" || item.status === "rejected" ? "high" : item.status === "completed_with_warnings" ? "warning" : "info",
      kind: item.title.toLowerCase().includes("provider") ? "provider" : item.title.toLowerCase().includes("workflow") ? "workflow" : "agent",
    }));
    const fromEvents = aggregateExecutionEvents(events);
    const recent = [...fromItems, ...fromEvents].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    return recent.slice(-400);
  }, [items, events]);

  const filteredItems = useMemo(() => {
    if (filter === "all") return merged;
    if (filter === "errors") return merged.filter((item) => item.severity === "high");
    if (filter === "agent") return merged.filter((item) => item.kind === "agent");
    if (filter === "provider") return merged.filter((item) => item.kind === "provider");
    return merged.filter((item) => item.kind === "workflow");
  }, [merged, filter]);

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return filteredItems.filter((item) => {
      const title = item.title.toLowerCase();
      if (!showRaw && (title.includes("log_emitted") || title.includes("low-level runtime events"))) return false;
      if (liveMode && item.kind === "other") return false;
      if (!q) return true;
      return item.title.toLowerCase().includes(q) || item.description.toLowerCase().includes(q);
    });
  }, [filteredItems, query, showRaw]);
  const liveItems = useMemo(() => (liveMode ? visibleItems.slice(-160) : visibleItems), [visibleItems, liveMode]);

  const rowHeight = compact ? 66 : 92;
  const overscan = 8;
  const viewportHeight = 448;
  const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const endIndex = Math.min(liveItems.length, startIndex + Math.ceil(viewportHeight / rowHeight) + overscan * 2);
  const windowed = liveItems.slice(startIndex, endIndex);
  const topSpacer = startIndex * rowHeight;
  const bottomSpacer = Math.max(0, (liveItems.length - endIndex) * rowHeight);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [filteredItems]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Execution Timeline</CardTitle>
        <CardDescription>Aggregated execution events with spam-collapsing and severity filters</CardDescription>
        <div className="sticky top-0 z-10 flex flex-wrap gap-2 rounded-md bg-background/90 py-1 backdrop-blur">
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
          <button type="button" className="rounded-md border px-2 py-1 text-xs" onClick={() => setCompact((v) => !v)}>
            <Badge variant={compact ? "default" : "muted"}>{compact ? "compact" : "detailed"}</Badge>
          </button>
          <button type="button" className="rounded-md border px-2 py-1 text-xs" onClick={() => setShowRaw((v) => !v)}>
            <Badge variant={showRaw ? "warning" : "muted"}>{showRaw ? "raw on" : "raw off"}</Badge>
          </button>
          <button type="button" className="rounded-md border px-2 py-1 text-xs" onClick={() => setLiveMode((v) => !v)}>
            <Badge variant={liveMode ? "default" : "muted"}>{liveMode ? "live mode" : "full mode"}</Badge>
          </button>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="search events"
            className="h-7 rounded-md border bg-background px-2 text-xs"
          />
          <button
            type="button"
            className="rounded-md border px-2 py-1 text-xs"
            onClick={() => {
              const index = liveItems.findIndex((item) => item.severity === "high");
              if (index < 0 || !scrollRef.current) return;
              scrollRef.current.scrollTop = index * rowHeight;
            }}
          >
            <Badge variant="destructive">jump failures</Badge>
          </button>
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={scrollRef}
          data-testid="execution-timeline-scroll"
          className="max-h-[28rem] overflow-y-auto pr-1"
          onScroll={(event) => setScrollTop((event.target as HTMLDivElement).scrollTop)}
        >
        <ol className="space-y-3">
          {topSpacer > 0 ? <li style={{ height: topSpacer }} /> : null}
          {windowed.map((item) => {
            const Icon = item.severity === "high" ? CircleAlert : item.severity === "warning" ? CircleDot : Circle;
            return (
              <li key={item.id} className="grid grid-cols-[1.25rem_1fr] gap-2 rounded-md border p-2" style={{ minHeight: rowHeight - 10 }}>
                <Icon className="mt-0.5 h-4 w-4 text-primary" aria-hidden="true" />
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm font-medium">{item.title}</div>
                    <time className="text-xs text-muted-foreground">{formatDateTime(item.timestamp)}</time>
                  </div>
                  <p className={`mt-1 text-xs text-muted-foreground ${compact ? "line-clamp-1" : "line-clamp-3"}`}>{item.description}</p>
                </div>
              </li>
            );
          })}
          {bottomSpacer > 0 ? <li style={{ height: bottomSpacer }} /> : null}
        </ol>
        </div>
      </CardContent>
    </Card>
  );
}
