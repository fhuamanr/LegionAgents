# Changelog

All notable architecture increments for the Enterprise Multi-Agent Software Delivery Platform are tracked here.

## Unreleased

### Added

- Foundational contract system with typed Pydantic schemas for agents, artifacts, context, execution, memory, prompts, outputs, workflow state, ingestion, repository runtime, QA sandbox, approvals, observability, and deployment-facing APIs.
- Context loading system for markdown and Mermaid sources.
- Context engineering system with dynamic selection, compression, isolation, repository summaries, architecture summaries, token budgeting, memory-aware loading, and future vector retrieval compatibility.
- Shared memory system with short-term memory, long-term memory, execution history, ADR memory, bug memory, namespaces, thread awareness, agent isolation, checkpoint-compatible records, and vector-ready interfaces.
- LangGraph orchestration layer with typed graph state, supervisor routing, agent nodes, conditional edges, retry loops, QA rejection loops, workflow transitions, and execution metadata.
- Reusable runtime foundation with `BaseAgent`, `AgentExecutor`, prompt building, context assembly, output validation, retry engine, logging hooks, and tool registry.
- Executable Developer Agent runtime with dynamic markdown rule loading, repository analysis, structured development outputs, retry-safe execution, and telemetry hooks.
- Autonomous QA Agent runtime with test generation, Playwright/Selenium automation boundaries, screenshots, bug reporting, severity classification, evidence, logs, and coverage output contracts.
- Context-aware governance engine with global policies, agent-local policies, rule inheritance, local override rules, markdown policy loading, policy validation, and enterprise standards registry.
- Real-time execution streaming with async event bus, structured execution events, progress tracking, timelines, structured logs, and telemetry fan-out.
- FastAPI backend with modular routers for workflows, uploads, executions, agents, reports, approvals, observability, health checks, and WebSocket-ready execution streams.
- Next.js dashboard using TypeScript, Tailwind, Shadcn-style primitives, Lucide icons, dark mode, responsive layout, workflow visualization, agent status, execution timeline, live logs, QA reports, screenshots, docs, Mermaid diagrams, PR summaries, approval gates, and observability panels.
- User Story Ingestion Engine for markdown, txt, docx, pdf, and future Jira/Notion ingestion with parsing, normalization, epic/story extraction, acceptance criteria extraction, validation, and requirement classification.
- Autonomous Repository Engine with isolated workspaces, secure Git service layer, repository cloning, branch creation, diff analysis, commit generation, PR preparation, repository metadata extraction, summaries, and future GitHub/GitLab provider boundaries.
- QA Execution Sandbox architecture with isolated browser sessions, Playwright/Selenium driver boundaries, screenshot storage, execution recordings, logs, test evidence, secure artifact storage, retry-safe execution, and Docker/Kubernetes-ready configuration.
- Human Approval Workflow system with approval gates, manual reviews, workflow pauses, retry approvals, PR approvals, QA override approvals, reviewer tracking, approval metadata, execution resume decisions, LangGraph helpers, FastAPI APIs, and dashboard visualization.
- Observability and Telemetry architecture with structured logging support, metrics, traces, execution telemetry, workflow analytics, agent analytics, error tracking, token usage, prompt size tracking, Prometheus text output, OpenTelemetry-ready span export, Datadog-ready JSON, and Grafana-ready dashboard models.
- Production deployment architecture with backend, frontend, and QA sandbox Dockerfiles; local and production Compose files; environment templates; production configuration; future Kubernetes manifests; storage architecture; Redis/PostgreSQL extension points; and CI workflow.
- Deployment documentation with Mermaid diagrams for container topology, request/streaming flow, storage architecture, and CI/CD readiness.
- Full root Docker Compose platform with frontend, FastAPI backend, LangGraph runtime, PostgreSQL, Redis, Qdrant, Playwright sandbox, Selenium sandbox, MinIO object storage, Nginx reverse proxy, isolated networks, persistent volumes, hot reload, startup dependencies, and health checks.
- Development Dockerfiles for hot-reload backend, frontend, and Playwright sandbox containers.
- Nginx reverse proxy configuration for frontend, `/api/` backend traffic, health checks, and `/ws/` WebSocket upgrades.
- Local full-stack environment template and Docker Compose platform guide.
- Dynamic Governance Management system with editable gravity rules, anti-gravity rules, personalities, prompts, coding standards, and QA policies.
- Versioned governance persistence with local JSON storage, rollback support, reload event history, and database-ready repository abstraction.
- FastAPI governance management APIs for listing, saving, retrieving, version history, rollback, and reload history.
- Frontend governance dashboard page with markdown editor, preview, agent/global document selectors, version history, and rollback controls.
- AI Workspace Chat system with persisted conversations, markdown/text/PDF/DOCX upload records, URL ingestion references, Git repository references, repository path references, chat messages, and workflow triggering.
- Chat WebSocket streaming endpoint for conversation-scoped events and execution progress updates.
- Workspace frontend page with chat transcript, markdown-friendly rendering, attachment/reference panel, multi-source upload actions, and workflow trigger controls.

### Changed

- README now reflects the full platform architecture, deployment structure, observability, approvals, repository automation, QA sandboxing, and ingestion systems.
- Mermaid diagrams were expanded to show platform layers, delivery workflow, runtime execution, context/memory/governance, dashboard streaming, and production deployment.
- `.gitignore` now allows safe deployment environment templates while continuing to ignore real environment files and secrets.

### Verified

- Backend test suite: `67 passed`.
- Frontend typecheck: passed.
- Frontend production build: passed.
- Docker Compose local and production configurations: validated.
- Root full-platform Docker Compose configuration: validated.
- Dynamic governance management backend tests and frontend build: validated.
- Workspace chat backend tests and frontend build: validated.
- Kubernetes staging and production Kustomize overlays: rendered successfully.
