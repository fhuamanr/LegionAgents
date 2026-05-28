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
    let pending: ExecutionEvent[] = [];
    let timer: ReturnType<typeof setTimeout> | null = null;
    const flush = (): void => {
      if (pending.length === 0) return;
      const batch = pending;
      pending = [];
      setEvents((current) => [...batch.reverse(), ...current].slice(0, 800));
    };

    const stream = connectExecutionStream(workflowId, (event) => {
      pending.push(event);
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        flush();
      }, 120);
    });

    if (stream) {
      return () => {
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        flush();
        stream.close();
      };
    }

    return undefined;
  }, [workflowId]);

  return events;
}
