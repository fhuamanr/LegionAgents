# Enterprise Multi-Agent Software Delivery Platform

Python/LangGraph foundation for an enterprise-grade multi-agent software delivery platform with a Next.js operational dashboard.

The platform is organized around specialized agents with isolated responsibilities:

- `ba`
- `architect`
- `developer`
- `qa`
- `docs`
- `pr`

The implementation currently focuses on reusable platform infrastructure: contracts, context engineering, shared memory, runtime execution, LangGraph orchestration, governance, real-time execution streaming, FastAPI APIs, and a frontend dashboard for monitoring workflows.

## Architecture

```text
agents/                  Agent-specific markdown rules, constraints, prompts, and diagrams
app/                     FastAPI backend platform
  dependencies/          Dependency injection providers
  middleware/            Request and telemetry middleware
  routers/               Workflow, execution, upload, agent, health, QA, docs, and PR APIs
  services/              Application services over core platform abstractions
  websocket/             WebSocket-ready execution event endpoints
core/
  agents/                Executable agent runtimes
    developer/           Developer Agent runtime
    qa/                  QA Agent runtime
  context/               Raw context loading and section classification
  context_engineering/   Smart context selection, compression, summaries, and budgeting
  contracts/             Pydantic schemas and output contracts
  governance/            Policy loading, inheritance, merging, validation, and standards registry
  graph/                 LangGraph orchestration infrastructure
  memory/                Shared memory system with local persistence
  prompts/               Prompt composition primitives
  runtime/               Reusable base runtime architecture
  streaming/             Execution event bus, telemetry, timelines, and structured logging
frontend/                Next.js, TypeScript, Tailwind, Shadcn-style dashboard
repository/              Shared repository standards
tests/                   Unit tests for platform foundations
workflows/               Future workflow definitions
outputs/                 Generated local runtime outputs
```

## Current Capabilities

- Typed Pydantic contracts for agents, artifacts, context, execution, memory, prompts, outputs, and workflow state.
- Context loading from markdown and Mermaid files.
- Context engineering with dynamic selection, compression, token budgeting, repository summaries, architecture summaries, memory retrieval, and leakage prevention.
- Shared memory system with short-term memory, long-term memory, execution history, ADR memory, bug memory, checkpoint-compatible records, namespaces, and vector-ready interfaces.
- LangGraph orchestration with supervisor routing, conditional edges, retry loops, QA rejection loops, workflow transition metadata, and minimal shared graph state.
- Reusable runtime foundation with `BaseAgent`, `AgentExecutor`, prompt building, context assembly, output validation, retry engine, logging hooks, and tool registry.
- Executable Developer Agent runtime with dynamic markdown rule loading, repository analysis, structured outputs, retry-safe execution, and telemetry hooks.
- Autonomous QA Agent runtime with unit, integration, Playwright, Selenium, screenshot, bug report, severity, evidence, and coverage output contracts.
- Agent Governance Engine with global policies, local override controls, rule inheritance, policy merging, standards registry, markdown loading, and runtime validation.
- Real-time execution streaming with async event bus, execution tracker, timeline generator, structured logging, telemetry layer, and WebSocket-ready events.
- FastAPI backend with modular routers for workflows, executions, uploads, agent status, health checks, QA reports, generated docs, PR summaries, and WebSocket execution events.
- Next.js dashboard with workflow visualization, agent status monitoring, execution timelines, live logs, QA reports, screenshot evidence, generated documentation, Mermaid diagrams, and PR visualization.

## Default Workflow

```text
BA -> Architect -> Developer -> QA -> Docs -> PR
```

The orchestration layer also supports:

- QA rejection loop: `QA -> Developer -> QA`
- retry execution
- conditional routing through route metadata
- isolated agent execution
- minimal shared graph state
- execution metadata for UI/API consumers

## Backend API

The FastAPI application is located in `app/`.

Run the backend:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Core API areas:

- workflow upload and triggering
- execution status and logs
- agent status
- QA report retrieval
- generated documentation retrieval
- PR summary retrieval
- health checks
- WebSocket-ready execution streams

## Frontend Dashboard

The dashboard is located in `frontend/` and uses:

- Next.js App Router
- TypeScript
- Tailwind CSS
- Shadcn-style UI primitives
- Lucide icons
- Mermaid rendering
- WebSocket-ready execution streaming

Run the dashboard:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000/dashboard
```

Optional integration variables:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8000
```

Without those variables, the dashboard uses typed mock data so the UI remains executable during backend integration.

## Agent Rule Loading

Developer runtime reads:

- `agents/developer/gravity.md`
- `agents/developer/anti-gravity.md`
- `agents/developer/coding-standards.md`
- `agents/developer/architecture.md`
- `agents/developer/forbidden.md`
- `agents/developer/naming.md`
- `agents/developer/testing.md`
- `agents/developer/security.md`

QA runtime reads:

- `agents/qa/gravity.md`
- `agents/qa/anti-gravity.md`
- `agents/qa/severity-rules.md`
- `agents/qa/test-strategy.md`

## Setup

Install backend dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm.cmd install
```

## Verification

Run backend tests:

```powershell
python -m pytest -p no:cacheprovider tests
```

Run frontend checks:

```powershell
cd frontend
npm.cmd run typecheck
npm.cmd run build
```

Current test coverage validates:

- contract imports and schema behavior
- context loading
- context engineering
- memory isolation and retrieval
- LangGraph orchestration
- runtime foundation
- Developer Agent runtime
- QA Agent runtime
- governance policy loading, inheritance, merging, and validation
- execution streaming, timelines, logs, and telemetry
- FastAPI backend routing and service boundaries
- frontend type safety and production build

## Extension Points

- Add external persistence by implementing `MemoryRepository`.
- Add Redis/PostgreSQL adapters behind the memory abstractions.
- Add vector database support by implementing `VectorMemoryRepository`.
- Add real browser automation by implementing `BrowserAutomationDriver`.
- Add model providers by implementing `AgentModelClient`.
- Add governance YAML support behind the policy loader.
- Add WebSocket delivery adapters over the streaming event bus.
- Add GitLab SaaS integration behind PR and workflow service adapters.
- Add new specialized agents by creating isolated runtime packages under `core/agents/`.

## Design Principles

- Do not collapse agent responsibilities.
- Keep prompts modular and agent-specific.
- Keep orchestration separate from business logic.
- Keep context isolated per agent.
- Keep memory thread-aware and agent-isolated.
- Prefer reusable abstractions and typed contracts.
- Use async-first execution boundaries.
- Keep local infrastructure replaceable by production adapters.
