# Multi-Agent Delivery Dashboard

Next.js dashboard for monitoring the enterprise multi-agent delivery platform.

## Architecture

- `app/` contains App Router pages for overview, executions, QA, docs, and PR views.
- `components/` contains reusable layout and Shadcn-style UI primitives.
- `features/` contains domain-specific dashboard modules, grouped by capability.
- `hooks/` contains client-side runtime hooks, including execution streaming.
- `lib/` contains typed contracts, API adapters, realtime adapters, and utilities.
- `types/` contains project-level type compatibility declarations.

## Integration Points

- `NEXT_PUBLIC_API_BASE_URL` enables REST-backed dashboard snapshots from `/dashboard/snapshot` and workflow telemetry from `/executions/{workflow_id}/telemetry`.
- `NEXT_PUBLIC_WS_BASE_URL` enables live execution events from `/ws/executions/{workflow_id}` and live graph snapshots from `/ws/workflows/{workflow_id}/telemetry`.
- `FRONTEND_DEBUG_OVERLAY=false` (or `NEXT_PUBLIC_FRONTEND_DEBUG_OVERLAY=false`) hides intrusive Next.js dev overlay/build indicators for demo mode while preserving browser console errors and backend logs.
- Execution sockets receive real event history first, then live `agent_started`, `agent_completed`, `agent_failed`, `retry_started`, `log_emitted`, `progress_updated`, `token_streamed`, `output_generated`, and `telemetry_recorded` events.
- The execution view visualizes running, completed, and failed agents; retries; live logs; streamed model tokens; generated outputs; and QA telemetry.
- Without environment variables, execution views render an empty live-state shell instead of simulated workflow activity.

## Verification

```bash
npm.cmd run typecheck
npm.cmd run build
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```
