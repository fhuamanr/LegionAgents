# Enterprise Multi-Agent Software Delivery Platform

Python 3.12+/LangGraph foundation for an enterprise software delivery control plane. The platform coordinates specialized agents, repository automation, QA evidence, governance, approvals, prompt operations, security, audit, and a Next.js dashboard.

Specialized agents remain isolated:

- `ba`
- `architect`
- `developer`
- `qa`
- `docs`
- `pr`

## Quick Start

Docker Compose is the canonical local runtime. It starts the frontend, FastAPI backend, LangGraph worker placeholder, PostgreSQL, Redis, Qdrant, MinIO, Playwright sandbox, Selenium sandbox, and Nginx reverse proxy.

```powershell
copy deployment\env\.env.compose.example .env.compose
docker compose --env-file .env.compose up --build
```

Open:

```text
Dashboard:       http://127.0.0.1:8080/dashboard
Backend API:     http://127.0.0.1:8080/api/health
Frontend direct: http://127.0.0.1:3000/dashboard
Backend direct:  http://127.0.0.1:8000/health
MinIO console:   http://127.0.0.1:9001
Selenium grid:   http://127.0.0.1:4444
```

Stop or reset:

```powershell
docker compose --env-file .env.compose down
docker compose --env-file .env.compose down --volumes
```

## Architecture

```text
agents/                  Agent-specific markdown rules, prompts, policies, diagrams
app/                     FastAPI application, routers, services, middleware, websocket
core/                    Clean architecture platform foundation
  agents/                Executable Developer and QA runtimes
  approvals/             Human gates, pauses, resume decisions
  chat/                  AI workspace chat and workflow triggering
  context*/              Context loading, compression, budgeting, isolation
  contracts/             Typed Pydantic contracts
  governance*/           Policy inheritance, validation, editable configs
  graph/                 LangGraph orchestration infrastructure
  ingestion/             Story/document ingestion pipeline
  memory/                Memory plus semantic intelligence and vector boundaries
  pr_review/             Autonomous PR review and readiness scoring
  prompt_studio/         Prompt editing, testing, versioning, comparison, rollback
  qa_sandbox/            Playwright/Selenium evidence sandbox
  repository*/           Git runtime and repository intelligence
  runtime/               Base agent runtime abstractions
  security/              JWT, RBAC, immutable audit
  streaming/             Event bus, logs, timelines, telemetry
  workspaces/            Tenant-aware projects, repositories, permissions, config
deployment/              Docker, Compose, env templates, Nginx, Kubernetes-ready assets
frontend/                Next.js dashboard
tests/                   Backend foundation tests
```

## System Map

```mermaid
flowchart TB
  User["User / Delivery Lead"] --> UI["Next.js Dashboard"]
  UI --> API["FastAPI Backend"]
  UI -. "WebSocket" .-> Stream["Streaming Bus"]

  API --> Security["Security + Audit"]
  API --> Workspaces["Multi-Workspace Management"]
  API --> Chat["Workspace Chat"]
  API --> PromptStudio["Prompt Studio"]
  API --> Governance["Governance"]
  API --> Graph["LangGraph Orchestrator"]
  API --> Observability["Observability"]

  Workspaces --> Isolation["Storage / Memory / Governance Namespaces"]
  Security --> RBAC["JWT + RBAC"]
  Security --> Audit["Immutable Audit Events"]

  Graph --> Runtime["Agent Runtime Foundation"]
  Runtime --> BA["BA"]
  Runtime --> Architect["Architect"]
  Runtime --> Developer["Developer"]
  Runtime --> QA["QA"]
  Runtime --> Docs["Docs"]
  Runtime --> PR["PR"]

  Runtime --> Context["Context Engineering"]
  Runtime --> Memory["Semantic Memory"]
  Runtime --> Repo["Repository Runtime + Intelligence"]
  Runtime --> Sandbox["QA Sandbox"]
  Runtime --> Reviews["Autonomous PR Review"]

  Stream --> Timeline["Timeline / Logs / Telemetry"]
  Sandbox --> Evidence["Screenshots / Videos / Logs"]
  Repo --> Git["Secure Git Operations"]
```

## Delivery Flow

```mermaid
flowchart LR
  Input["Stories / Docs / URLs / Repos"] --> Ingestion["Ingestion + Normalization"]
  Ingestion --> BA["BA: stories + acceptance criteria"]
  BA --> Architect["Architect: decisions + constraints"]
  Architect --> Developer["Developer: implementation output"]
  Developer --> Repo["Repository Runtime: branch / diff / commit / PR package"]
  Repo --> Review["Autonomous PR Review"]
  Review --> QA["QA: tests + evidence"]
  QA --> Sandbox["Playwright / Selenium Sandbox"]
  Sandbox --> QA
  QA -->|approved| Docs["Docs"]
  QA -->|rejected| Developer
  Docs --> Approval["Human Approval Gate"]
  Approval --> PR["PR Summary / Merge Readiness"]
```

## Enterprise Boundaries

```mermaid
flowchart TB
  Tenant["Tenant"] --> Workspace["Workspace"]
  Workspace --> Projects["Projects"]
  Projects --> Repos["Repositories"]
  Workspace --> Agents["Workspace Agent Config"]
  Workspace --> Permissions["Members / Roles / Permissions"]
  Workspace --> Config["Workspace Configuration"]

  Config --> Storage["Isolated Storage Root"]
  Config --> MemoryNS["Isolated Memory Namespace"]
  Config --> GovernanceNS["Isolated Governance Namespace"]

  Security["Security Middleware"] --> Principal["Auth Principal"]
  Principal --> RBAC["RBAC Policy"]
  RBAC --> APIs["Protected API Dependencies"]
  APIs --> Audit["Immutable Audit Log"]

  Audit --> PromptTrail["Prompt Audit Trail"]
  Audit --> AgentTrail["Agent Execution Audit"]
  Audit --> ApprovalTrail["Approval Audit"]
  Audit --> WorkflowTrail["Workflow Audit History"]
```

## Docker Compose Topology

```mermaid
flowchart TB
  Browser["Browser"] --> Nginx["Nginx :8080"]
  Nginx --> Frontend["Next.js :3000"]
  Nginx --> Backend["FastAPI :8000"]
  Frontend -. "WS / HTTP" .-> Backend

  Backend --> LangGraph["LangGraph Runtime"]
  Backend --> Postgres["PostgreSQL"]
  Backend --> Redis["Redis"]
  Backend --> Qdrant["Qdrant"]
  Backend --> MinIO["MinIO"]
  Backend --> Playwright["Playwright Sandbox"]
  Backend --> Selenium["Selenium Sandbox"]

  Playwright --> Artifacts["QA Artifacts"]
  Selenium --> Artifacts
  Artifacts --> MinIO
```

## Capabilities

- **Orchestration:** LangGraph supervisor, typed graph state, conditional routing, retries, QA rejection loops, workflow metadata.
- **Agent Runtime:** reusable base runtime, Developer runtime, QA runtime, prompt building, context assembly, output validation, retries, telemetry hooks.
- **Context and Memory:** markdown loading, context compression, token budgeting, isolated agent context, short/long-term memory, ADR/bug/execution history memory, semantic indexing, vector-ready retrieval, Qdrant-ready boundary.
- **Workspace and Project Management:** tenant-aware workspaces, projects, repository bindings, workspace permissions, workspace-specific agent config, isolated storage/memory/governance namespaces.
- **Repository Automation:** isolated Git workspaces, clone/branch/diff/commit/PR preparation, repository scanning, framework detection, dependency graphing, architecture summaries.
- **Quality and Review:** autonomous QA output contracts, Playwright/Selenium sandbox boundaries, screenshot/log/evidence artifacts, autonomous PR review, structured comments, severity classification, merge readiness scoring.
- **Governance and Prompts:** global and agent policies, inheritance, policy validation, editable governance UI, Prompt Engineering Studio with markdown editing, variables, preview, testing, versioning, comparison, rollback, token estimation.
- **Security and Audit:** JWT auth boundary, RBAC roles/permissions, optional security middleware, route dependency helpers, immutable hash-chained audit events, audit APIs.
- **Observability and Streaming:** execution event bus, live logs, timelines, workflow telemetry, metrics, traces, analytics, Prometheus/OpenTelemetry/Datadog/Grafana-ready outputs.
- **Dashboard:** Next.js App Router UI for workspaces, chat, workflows, prompts, governance, approvals, observability, QA reports, docs, PR summaries, Mermaid diagrams.

## API Areas

- `/auth/*` and `/audit/*`: JWT, access checks, audit events
- `/workspaces/*`: tenants, workspaces, projects, repository bindings, isolation summary
- `/workspace/chat/*`: chat conversations, uploads, references, workflow triggering
- `/workflows/*` and `/executions/*`: workflow lifecycle, status, logs, telemetry
- `/approvals/*`: gates, decisions, pauses, resumes
- `/governance/configs/*`: editable governance, versions, rollback
- `/prompt-studio/prompts/*`: prompt CRUD, preview, testing, versions, compare, rollback
- `/observability/*`: metrics, traces, analytics, exporters
- `/reports/*`, `/docs/*`, `/pr/*`: QA reports, generated docs, PR summaries
- `/ws/*`: execution, workflow telemetry, chat streams

## Local Development

Backend:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Optional frontend integration:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8000
```

Without those variables, the dashboard uses typed mock data.

## Verification

Backend:

```powershell
python -m pytest -p no:cacheprovider tests
```

Frontend:

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

Latest verified backend suite: `89 passed`.

## Deployment Assets

- Root local stack: `docker-compose.yml`
- Dockerfiles: `deployment/docker/`
- Nginx: `deployment/nginx/nginx.conf`
- Env templates: `deployment/env/`
- Production config: `deployment/config/`
- Compose docs: `deployment/docs/docker-compose-platform.md`
- Production guide: `deployment/docs/production-deployment.md`
- Kubernetes-ready manifests: `deployment/kubernetes/`

## Design Principles

- Never collapse agent responsibilities.
- Keep prompts modular and agent-specific.
- Keep orchestration, memory, context, prompts, governance, and execution separate.
- Keep tenant/workspace boundaries explicit.
- Keep audit events immutable.
- Prefer typed contracts and async-first boundaries.
- Keep local in-memory implementations replaceable by Redis, PostgreSQL, Qdrant, object storage, and enterprise identity providers.
