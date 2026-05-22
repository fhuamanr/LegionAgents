# Changelog

All notable architecture increments for the Enterprise Multi-Agent Software Delivery Platform are tracked here.

## Unreleased

### Platform Foundation

- Added typed Pydantic contracts for agents, artifacts, context, execution, memory, prompts, outputs, workflow state, ingestion, repository operations, QA sandboxing, approvals, observability, deployment, workspaces, prompt studio, PR review, and security/audit.
- Added reusable async runtime foundation with `BaseAgent`, `AgentExecutor`, prompt building, context assembly, output validation, retry engine, logging hooks, and tool registry.
- Added LangGraph orchestration infrastructure with typed state, supervisor routing, agent nodes, conditional edges, retry loops, QA rejection loops, and workflow metadata.

### Agent Systems

- Added executable Developer Agent runtime with markdown rule loading, repository analysis, structured development outputs, retries, and telemetry hooks.
- Added autonomous QA Agent runtime with unit/integration/browser test output contracts, Playwright/Selenium boundaries, screenshots, bug reports, severity classification, evidence, logs, and coverage summaries.

### Context, Memory, and Governance

- Added context loading for markdown and Mermaid sources.
- Added context engineering with dynamic selection, compression, token budgeting, repository/architecture summaries, memory-aware loading, and context leakage prevention.
- Added shared memory system with short-term, long-term, execution history, ADR, bug, checkpoint, namespace, and vector-ready memory.
- Added Multi-Agent Memory Intelligence with semantic indexing, retrieval, historical bug memory, ADR memory, coding pattern memory, QA learning memory, execution history indexing, and Qdrant-ready vector store boundaries.
- Added governance engine with global/local policies, inheritance, override controls, markdown loading, standards registry, merging, and runtime validation.
- Added dynamic governance management APIs and dashboard with version history, rollback, reload events, and local JSON persistence.

### Workspaces, Security, and Audit

- Added tenant-aware multi-workspace architecture with projects, repository bindings, workspace permissions, workspace-specific agents, and isolated storage/memory/governance namespaces.
- Added Enterprise Security and Audit system with JWT service, RBAC roles/permissions, optional security middleware, route dependency helpers, immutable hash-chained audit events, and audit APIs.

### Repository, Review, and Delivery Automation

- Added Autonomous Repository Engine with isolated workspaces, secure Git commands, cloning, branching, diff analysis, commit generation, PR preparation, metadata extraction, and provider boundaries.
- Added Repository Intelligence Engine with local/mounted scanning, future GitHub boundary, architecture detection, framework detection, dependency graph generation, module relationships, and summaries.
- Added Autonomous PR Review System with architecture, coding standards, QA, security, documentation validation, structured review comments, severity classification, and merge readiness scoring.
- Added User Story Ingestion Engine for markdown, txt, docx, pdf, and future Jira/Notion adapters with parsing, normalization, story/epic extraction, acceptance criteria extraction, validation, and classification.

### QA, Approvals, Observability, and Streaming

- Added QA Execution Sandbox architecture with isolated Playwright/Selenium sessions, screenshots, videos, logs, evidence, artifact storage, retry safety, and Docker/Kubernetes-ready configuration.
- Added Human Approval Workflow with approval gates, manual reviews, retry approvals, PR approvals, QA override approvals, workflow pauses, reviewer tracking, metadata, and resume decisions.
- Added real-time execution streaming with async event bus, structured events, progress tracking, timelines, structured logs, telemetry fan-out, WebSocket-ready streams, and live workflow graph snapshots.
- Added real streaming execution visualization components: `/workflows/live` for immediate workflow id handoff, `/dashboard/snapshot` for the latest real dashboard state, `/ws/executions/{workflow_id}` with history replay plus live events, `/ws/workflows/{workflow_id}/telemetry` with live graph snapshots, OpenAI token chunk streaming, generated output events, QA telemetry events, retry/status tracking, and frontend panels for tokens, outputs, QA results, logs, running/completed/failed agents, and retries.
- Added observability architecture with structured logging, metrics, tracing, workflow analytics, agent analytics, error tracking, token usage, prompt size tracking, Prometheus text output, OpenTelemetry-ready spans, Datadog-ready JSON, and Grafana-ready dashboard models.

### Prompt and Dashboard Experience

- Added Prompt Engineering Studio with prompt editing, markdown support, variable injection, live testing, execution preview, token estimation, versioning, comparison, rollback, and APIs/UI.
- Added AI Workspace Chat with persisted conversations, uploads, URL references, Git references, repository path references, chat events, WebSocket streaming, and workflow triggering.
- Added Next.js dashboard with workspace management, chat, workflow visualization, live logs, execution timelines, agent status, approvals, observability, QA reports, screenshots, generated docs, PR summaries, Mermaid rendering, governance editor, and Prompt Studio.
- Removed dummy execution visualization from the frontend: mock dashboard data, client-side replay timers, synthetic event refreshes, and fake execution motion were replaced by real API snapshots, WebSocket streams, and an empty live-state shell when no backend is configured.

### Deployment

- Added production deployment architecture with backend, frontend, QA sandbox Dockerfiles, local/prod Compose assets, environment templates, production config, CI workflow, Kubernetes-ready manifests, storage architecture, Redis/PostgreSQL extension points, and object storage boundaries.
- Added root Docker Compose stack with frontend, FastAPI backend, LangGraph runtime, PostgreSQL, Redis, Qdrant, Playwright sandbox, Selenium sandbox, MinIO, Nginx reverse proxy, isolated networks, persistent volumes, hot reload, health checks, and startup dependencies.

### Changed

- Refactored README into an operator-focused overview with optimized Mermaid diagrams, concise capability map, Docker-first startup commands, and current API/UI surfaces.
- Updated README, frontend README, and Mermaid diagrams to document the real live streaming execution path, dashboard snapshot service, token stream, generated outputs, QA telemetry, event history replay, and live workflow start endpoint.
- Stabilized Developer Agent repository prompt context as the platform grew by increasing repository scan coverage and surfacing key developer runtime files separately.
- `.gitignore` keeps real secrets ignored while allowing safe deployment environment templates.

### Verified

- Backend suite: `89 passed`.
- Frontend typecheck: passed.
- Docker Compose configuration and deployment assets validated structurally.
