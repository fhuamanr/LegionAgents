# Multi-Agent Delivery Dashboard

Next.js dashboard for monitoring the enterprise multi-agent delivery platform.

## Architecture

- `app/` contains App Router pages for overview, executions, QA, docs, and PR views.
- `components/` contains reusable layout and Shadcn-style UI primitives.
- `features/` contains domain-specific dashboard modules, grouped by capability.
- `hooks/` contains client-side runtime hooks, including execution streaming.
- `lib/` contains typed contracts, API adapters, realtime adapters, utilities, and mock fallback data.
- `types/` contains project-level type compatibility declarations.

## Integration Points

- `NEXT_PUBLIC_API_BASE_URL` enables REST-backed dashboard snapshots.
- `NEXT_PUBLIC_WS_BASE_URL` enables live workflow execution events.
- Without environment variables, the dashboard uses typed mock data so the UI remains executable during backend integration.

## Verification

```bash
npm.cmd run typecheck
npm.cmd run build
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```
