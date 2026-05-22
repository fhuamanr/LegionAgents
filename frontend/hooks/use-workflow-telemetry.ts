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
    const stream = connectWorkflowTelemetryStream(workflowId, setSnapshot);

    if (stream) {
      return () => stream.close();
    }

    const interval = window.setInterval(() => {
      setSnapshot((current) => ({
        ...current,
        durationMs: current.durationMs + 5000,
        metadata: {
          ...current.metadata,
          lastClientRefresh: new Date().toISOString(),
        },
      }));
    }, 5000);

    return () => window.clearInterval(interval);
  }, [workflowId]);

  return snapshot;
}
