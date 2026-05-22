# Production Deployment Architecture

This deployment architecture keeps runtime concerns separated across backend APIs, frontend dashboard, QA sandbox execution, storage, observability, and future external persistence.

## Container Topology

```mermaid
flowchart TB
  User["User / Reviewer"] --> Frontend["Frontend Dashboard Container"]
  Frontend --> Backend["FastAPI Backend Container"]
  Frontend -. "WebSocket" .-> Backend

  Backend --> Outputs["Output Storage Volume"]
  Backend --> EventBus["In-Process Event Bus"]
  Backend --> Observability["Observability APIs"]
  Backend -. "future" .-> Redis["Redis"]
  Backend -. "future" .-> Postgres["PostgreSQL"]

  Backend --> QASandbox["QA Sandbox Container"]
  QASandbox --> QAArtifacts["QA Artifact Volume"]
  QASandbox --> Browser["Playwright / Selenium Browser Runtime"]

  Observability --> Prometheus["Prometheus Scrape"]
  Observability --> Datadog["Datadog Export"]
  Observability --> OTel["OpenTelemetry Export"]
  Prometheus --> Grafana["Grafana Dashboards"]
```

## Request And Streaming Flow

```mermaid
sequenceDiagram
  participant Browser as Dashboard Browser
  participant Frontend as Next.js Frontend
  participant API as FastAPI Backend
  participant Graph as LangGraph Runtime
  participant QA as QA Sandbox
  participant Store as Artifact Storage

  Browser->>Frontend: Open dashboard
  Frontend->>API: Fetch workflow snapshot
  Browser->>API: Open WebSocket stream
  API->>Graph: Trigger workflow
  Graph->>API: Emit structured execution events
  API-->>Browser: Stream live events
  Graph->>QA: Start isolated QA execution
  QA->>Store: Persist screenshots, videos, logs, evidence
  API->>Frontend: Serve reports and artifact metadata
```

## Environment Strategy

- `local`: developer-friendly Docker Compose, bind-mounted outputs, optional Redis/PostgreSQL profiles.
- `staging`: production-like Kubernetes overlay with low replica counts and isolated secrets.
- `production`: immutable images, secret-manager backed configuration, persistent storage, TLS at ingress/proxy, horizontal replicas.

Environment values are loaded from:

- `deployment/env/.env.local.example`
- `deployment/env/.env.production.example`
- Kubernetes `ConfigMap` and `Secret` objects
- Future enterprise secret stores such as Vault, AWS Secrets Manager, Azure Key Vault, or GCP Secret Manager

## Secrets Management

Never commit real secrets. Production secrets should be injected by the orchestrator.

Required secret classes:

- OpenAI/API provider keys
- application signing secret
- Redis password
- PostgreSQL password
- Datadog API key
- future GitHub/GitLab integration tokens

## Storage Architecture

```mermaid
flowchart LR
  Backend["Backend"] --> Outputs["Workflow Outputs"]
  Backend --> Logs["Structured Logs"]
  QASandbox["QA Sandbox"] --> Screenshots["Screenshots"]
  QASandbox --> Videos["Videos"]
  QASandbox --> Evidence["Test Evidence"]

  Outputs --> LocalVolume["Local Volume"]
  Screenshots --> LocalVolume
  Videos --> LocalVolume
  Evidence --> LocalVolume

  LocalVolume -. "future adapter" .-> ObjectStorage["S3 / Azure Blob / GCS"]
  Backend -. "future memory" .-> Redis["Redis"]
  Backend -. "future persistence" .-> Postgres["PostgreSQL"]
  Backend -. "future retrieval" .-> VectorDB["Vector Database"]
```

## Local Development

Build and run backend plus frontend:

```powershell
docker compose -f deployment/compose/docker-compose.local.yml up --build backend frontend
```

Run optional infrastructure:

```powershell
docker compose -f deployment/compose/docker-compose.local.yml --profile infra up --build
```

Run QA sandbox profile:

```powershell
docker compose -f deployment/compose/docker-compose.local.yml --profile qa up --build qa-sandbox
```

## Production Compose

Build images:

```powershell
docker build -f deployment/docker/backend/Dockerfile -t multi-agent-delivery-backend:latest .
docker build -f deployment/docker/frontend/Dockerfile -t multi-agent-delivery-frontend:latest .
docker build -f deployment/docker/qa-sandbox/Dockerfile -t multi-agent-delivery-qa-sandbox:latest .
```

Run production-like compose:

```powershell
docker compose --env-file deployment/env/.env.production.example -f deployment/compose/docker-compose.production.yml up -d
```

## Future Kubernetes

Kubernetes manifests are intentionally provider-neutral and Kustomize-ready:

```powershell
kubectl apply -k deployment/kubernetes/overlays/staging
kubectl apply -k deployment/kubernetes/overlays/production
```

Production ingress, certificate management, network policies, external Redis/PostgreSQL, and object storage should be added as environment-specific overlays.

## CI/CD Readiness

The GitHub Actions workflow validates:

- backend tests
- frontend typecheck
- frontend production build
- Docker image builds

The same stages map cleanly to GitLab SaaS CI:

```mermaid
flowchart LR
  Commit["Commit"] --> Test["Backend Tests"]
  Test --> Typecheck["Frontend Typecheck"]
  Typecheck --> Build["Frontend Build"]
  Build --> Images["Docker Image Build"]
  Images --> Scan["Security Scan"]
  Scan --> Deploy["Deploy to Staging / Production"]
```

## Secure Defaults

- containers run as non-root users
- production compose applies `no-new-privileges`
- Linux capabilities are dropped where practical
- runtime outputs are isolated to mounted volumes
- real secrets are excluded from Git
- QA artifacts are stored separately from API runtime outputs
- Redis/PostgreSQL are extension profiles until real adapters are enabled

