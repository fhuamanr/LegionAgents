# Enterprise Multi-Agent Software Delivery Platform

Python/LangGraph foundation for an enterprise-grade multi-agent software delivery platform.

The platform is organized around specialized agents with isolated responsibilities:

- `ba`
- `architect`
- `developer`
- `qa`
- `docs`
- `pr`

The current implementation focuses on reusable infrastructure: contracts, context engineering, shared memory, runtime execution, LangGraph orchestration, and executable Developer/QA agent runtimes.

## Architecture

```text
agents/                  Agent-specific markdown rules, constraints, prompts, and diagrams
core/
  agents/                Executable agent runtimes
    developer/           Developer Agent runtime
    qa/                  QA Agent runtime
  context/               Raw context loading and section classification
  context_engineering/   Smart context selection, compression, summaries, and budgeting
  contracts/             Pydantic schemas and output contracts
  graph/                 LangGraph orchestration infrastructure
  memory/                Shared memory system with local persistence
  prompts/               Prompt composition primitives
  runtime/               Reusable base runtime architecture
repository/              Shared repository standards
tests/                   Unit tests for platform foundations
workflows/               Future workflow definitions
outputs/                 Generated local runtime outputs
```

## Current Capabilities

- Typed Pydantic contracts for agents, artifacts, context, execution, memory, outputs, and workflow state.
- Context loading from markdown and Mermaid files.
- Context engineering with dynamic selection, compression, token budgeting, repository summaries, architecture summaries, memory retrieval, and leakage prevention.
- Shared memory system with short-term memory, long-term memory, execution history, ADR memory, bug memory, checkpoint-compatible records, and vector-ready interfaces.
- LangGraph orchestration with supervisor routing, conditional edges, retry loops, QA rejection loops, and workflow transition metadata.
- Reusable runtime foundation with `BaseAgent`, `AgentExecutor`, prompt building, context assembly, output validation, retry engine, and tool registry.
- Executable Developer Agent runtime.
- Autonomous QA Agent runtime with browser abstraction hooks for future Playwright/Selenium adapters.

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

```powershell
python -m pip install -r requirements.txt
```

## Run Tests

```powershell
python -m pytest -p no:cacheprovider tests
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

## Extension Points

- Add external persistence by implementing `MemoryRepository`.
- Add Redis/PostgreSQL adapters behind the memory abstractions.
- Add vector database support by implementing `VectorMemoryRepository`.
- Add real browser automation by implementing `BrowserAutomationDriver`.
- Add model providers by implementing `AgentModelClient`.
- Add new specialized agents by creating isolated runtime packages under `core/agents/`.

## Design Principles

- Do not collapse agent responsibilities.
- Keep prompts modular and agent-specific.
- Keep orchestration separate from business logic.
- Keep context isolated per agent.
- Prefer reusable abstractions and typed contracts.
- Use async-first execution boundaries.
- Keep local infrastructure replaceable by production adapters.
