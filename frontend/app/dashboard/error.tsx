"use client";

import { useEffect } from "react";

type DashboardErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function DashboardError({
  error,
  reset,
}: DashboardErrorProps): JSX.Element {
  useEffect(() => {
    // Keep full visibility in browser logs for debugging/telemetry.
    console.error("Dashboard runtime error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-foreground">
          Dashboard recovered from a runtime error
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          A non-blocking error occurred. Logs are still available in the browser
          console.
        </p>
        <button
          type="button"
          onClick={reset}
          className="mt-4 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Retry section
        </button>
      </div>
    </div>
  );
}
