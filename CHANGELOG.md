# Changelog

All notable architecture increments for the Enterprise Multi-Agent Software Delivery Platform are tracked here.

## v0.1.0-alpha - 2026-05-23

First public alpha release focused on turning Legion Agents into a real MVP: configurable, demonstrable, observable, and usable end to end.

### Current Operational Status

- Added alpha stabilization recovery for governance preload breadth, provider CRUD reliability, multi-file upload handling, and workflow context hydration from uploaded documents.
- Added startup seeding/logging behavior so governance markdown documents are discovered and seeded deterministically from mounted repository paths.
- Added an end-to-end MVP demo verifier script (`scripts/mvp_demo_verifier.py`) that validates health/readiness, governance edit/versioning, provider CRUD, upload, chat-triggered workflow, execution logs, and report generation.
- Converted platform persistence from local-only defaults to PostgreSQL-backed production adapters for workflow executions/checkpoints, API workflow/upload state, Prompt Studio documents and versions, governance documents and versions, workspaces, projects, and workspace agent configuration.
- Added a shared PostgreSQL JSONB document store adapter used by production repositories while preserving in-memory implementations for focused tests.
- Replaced the Docker Compose LangGraph worker placeholder with a real `core.graph.worker` process that recovers persisted running workflow executions.
- Wired active Prompt Studio documents into runtime agent context so prompt edits can affect subsequent executions without restarting.
- Wired runtime-edited governance documents into the effective policy so global and agent rule edits participate in inheritance, prompt generation, runtime validation, output validation, and execution rejection.
- Added file upload ingestion for markdown, txt, DOCX, and PDF inputs through the backend upload API.
- Added configurable multi-provider LLM runtime support with OpenAI-compatible routing for OpenAI/Codex, Cursor-compatible APIs, OpenRouter, Ollama, LM Studio, local providers, and custom endpoints.
- Added provider registry persistence, masked API key responses, provider health checks, readiness checks, runtime model overrides, and agent-specific model selection.
- Added provider management UI at `/dashboard/providers` plus `/providers` and `/providers/health` APIs.
- Updated root Mermaid architecture to reflect real PostgreSQL persistence, runtime prompt/governance reload behavior, and the real LangGraph worker.
- Updated root Mermaid architecture to show provider management, provider persistence, runtime provider registry, and multi-provider model routing.
- Added Apache License 2.0 project licensing.

### Currently Working

- Real `BA -> Architect -> Developer -> QA -> Docs -> PR` workflow execution through LangGraph.
- Real multi-provider model execution with structured outputs, retries, token streaming, and generated output events.
- Real provider configuration from environment variables, UI, and backend APIs.
- Real repository modification path for cloning, branching, applying generated changes, diffing, committing, and preparing PR artifacts.
- Real QA runtime contracts, sandbox boundaries, logs, screenshots, and evidence artifacts when local sandbox services are available.
- Real live workflow visualization from backend snapshots and WebSocket event streams.
- Real context engineering with dynamic loading, token budgeting, repository summarization, semantic file selection, architecture-aware prioritization, and agent isolation.
- Real governance enforcement that injects policy into prompts and rejects invalid outputs at execution time.
- Real Prompt Studio and governance versioning with rollback.

### Backlog

- Move execution event history from the in-process event bus to Redis Streams or persisted PostgreSQL event replay for multi-process streaming durability.
- Implement hosted GitHub/GitLab PR creation; current repository runtime prepares local PR artifacts and metadata.
- Implement Jira and Notion ingestion adapters.
- Publish all downloadable artifacts through MinIO/object storage.
- Connect JWT/RBAC to an external identity provider for production SSO.
- Complete Qdrant-backed semantic retrieval as the default memory backend.
- Expand frontend editing coverage for every workflow/runtime execution setting.
- Add Docker Compose smoke tests that exercise PostgreSQL, worker recovery, and sandbox services in CI.

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

- Alpha MVP verifier tests: governance seed/idempotency, provider CRUD regression, and multi-file upload API checks passed.
- Backend suite: `89 passed`.
- Focused provider/API workflow suite: passed.
- Frontend typecheck: passed.
- Docker Compose configuration and deployment assets validated structurally.
