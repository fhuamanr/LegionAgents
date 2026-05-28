"use client";

import { useEffect, useState } from "react";
import { connectWorkflowTelemetryStream } from "@/lib/realtime";
import type { WorkflowTelemetrySnapshot } from "@/lib/types";

export function useWorkflowTelemetry(
  workflowId: string,
  seedSnapshot: WorkflowTelemetrySnapshot,
): WorkflowTelemetrySnapshot {
  const [snapshot, setSnapshot] = useState<WorkflowTelemetrySnapshot>(seedSnapshot);

  useEffect(() => {
    setSnapshot(seedSnapshot);
  }, [seedSnapshot]);

  useEffect(() => {
    let latest: WorkflowTelemetrySnapshot | null = null;
    let rafId: number | null = null;
    const flush = (): void => {
      if (!latest) return;
      setSnapshot(latest);
      latest = null;
      rafId = null;
    };
    const stream = connectWorkflowTelemetryStream(workflowId, (incoming) => {
      latest = incoming;
      if (rafId != null) return;
      rafId = window.requestAnimationFrame(flush);
    });

    if (stream) {
      return () => {
        if (rafId != null) {
          window.cancelAnimationFrame(rafId);
          rafId = null;
        }
        flush();
        stream.close();
      };
    }

    return undefined;
  }, [workflowId]);

  return snapshot;
}
