"use client";

import { useEffect, useState } from "react";
import { connectExecutionStream } from "@/lib/realtime";
import type { ExecutionEvent } from "@/lib/types";

export function useExecutionStream(workflowId: string, seedEvents: readonly ExecutionEvent[]): readonly ExecutionEvent[] {
  const [events, setEvents] = useState<readonly ExecutionEvent[]>(seedEvents);

  useEffect(() => {
    setEvents(seedEvents);
  }, [seedEvents]);

  useEffect(() => {
    const stream = connectExecutionStream(workflowId, (event) => {
      setEvents((current) => [event, ...current].slice(0, 50));
    });

    if (stream) {
      return () => stream.close();
    }

    return undefined;
  }, [workflowId]);

  return events;
}
