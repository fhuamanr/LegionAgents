"use client";

import { useEffect, useMemo, useState } from "react";
import { connectExecutionStream } from "@/lib/realtime";
import type { ExecutionEvent } from "@/lib/types";

export function useExecutionStream(workflowId: string, seedEvents: readonly ExecutionEvent[]): readonly ExecutionEvent[] {
  const [events, setEvents] = useState<readonly ExecutionEvent[]>(seedEvents);
  const fallbackEvents = useMemo(() => seedEvents, [seedEvents]);

  useEffect(() => {
    const stream = connectExecutionStream(workflowId, (event) => {
      setEvents((current) => [event, ...current].slice(0, 50));
    });

    if (stream) {
      return () => stream.close();
    }

    let index = 0;
    const interval = window.setInterval(() => {
      const event = fallbackEvents[index % fallbackEvents.length];
      setEvents((current) => [
        {
          ...event,
          id: `${event.id}-replay-${Date.now()}`,
          timestamp: new Date().toISOString(),
        },
        ...current,
      ].slice(0, 50));
      index += 1;
    }, 9000);

    return () => window.clearInterval(interval);
  }, [fallbackEvents, workflowId]);

  return events;
}
