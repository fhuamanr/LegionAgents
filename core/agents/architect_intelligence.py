"""Solution-architect intelligence helpers."""

from __future__ import annotations

import json
from typing import Any


def build_architect_bundle(*, task: str, ba_index: dict[str, Any], ba_docs: dict[str, str], structured_output: dict[str, Any]) -> dict[str, Any]:
    stack = _infer_stack(task, ba_docs)
    modules = _module_model()
    docs: dict[str, str] = {
        "architecture.md": _architecture_md(task, stack),
        "module_decomposition.md": _module_decomposition_md(modules),
        "bounded_contexts.md": _bounded_contexts_md(),
        "api_contracts.md": _api_contracts_md(),
        "openapi_draft.yaml": _openapi_yaml(),
        "database_design.md": _database_design_md(),
        "frontend_architecture.md": _frontend_architecture_md(),
        "backend_architecture.md": _backend_architecture_md(),
        "event_flow_architecture.md": _event_flow_md(),
        "security_architecture.md": _security_md(),
        "observability_plan.md": _observability_md(),
        "deployment_architecture.md": _deployment_md(),
        "technical_risks.md": _technical_risks_md(),
        "developer_handoff.md": _developer_handoff_md(stack),
        "architect_quality_report.md": _quality_report_md(),
    }
    docs.update(_adr_docs())
    diagrams = _diagram_bundle()
    return {
        "stack": stack,
        "modules": modules,
        "docs": docs,
        "diagrams": diagrams,
        "ba_index_used": bool(ba_index),
    }


def _infer_stack(task: str, ba_docs: dict[str, str]) -> dict[str, str]:
    text = f"{task}\n{json.dumps(ba_docs)}".lower()
    frontend = "React + TypeScript + React Query + Zod"
    backend = "Python FastAPI + SQLAlchemy + Alembic"
    db = "PostgreSQL"
    if "node" in text or "nestjs" in text:
        backend = "Node.js + NestJS + Prisma"
    return {"frontend": frontend, "backend": backend, "database": db}


def _module_model() -> list[dict[str, str]]:
    return [
        {"name": "Identity", "responsibility": "auth/session/roles", "apis": "/api/auth/*", "data": "users, roles, sessions"},
        {"name": "Catalog", "responsibility": "products/search/filter", "apis": "/api/products/*", "data": "products, inventory"},
        {"name": "Cart", "responsibility": "cart state and totals", "apis": "/api/cart/*", "data": "carts, cart_items"},
        {"name": "Checkout", "responsibility": "order creation + payment orchestration", "apis": "/api/checkout", "data": "orders, order_items, payments"},
        {"name": "Orders", "responsibility": "order lifecycle and history", "apis": "/api/orders/*", "data": "orders, shipments"},
        {"name": "Notifications", "responsibility": "email/app notifications", "apis": "/api/notifications/*", "data": "notification_events"},
        {"name": "Admin", "responsibility": "product/report ops", "apis": "/api/admin/*", "data": "catalog + analytics views"},
    ]


def _architecture_md(task: str, stack: dict[str, str]) -> str:
    return (
        "# Architecture\n\n"
        "## System Overview\n"
        f"{task.strip()}\n\n"
        "The solution is a modular monolith for MVP speed with explicit bounded-context seams to enable future extraction of Checkout/Payments.\n\n"
        "## Architecture Style\n"
        "- Modular monolith with Clean Architecture boundaries per module.\n"
        "- Sync request/response for core flows, domain events for side effects.\n"
        "- Idempotent checkout and payment commands.\n\n"
        "## Frontend Architecture\n"
        f"- Stack: {stack['frontend']}.\n"
        "- Route groups: public, authenticated, admin.\n"
        "- Data layer: typed API client + cache invalidation rules.\n"
        "- Validation: shared schema contracts for form and API payloads.\n\n"
        "## Backend Architecture\n"
        f"- Stack: {stack['backend']}.\n"
        "- Layers: interface -> application -> domain -> infrastructure.\n"
        "- Use cases own orchestration; repositories own persistence.\n"
        "- Centralized error taxonomy and RFC7807-style responses.\n\n"
        "## Database Architecture\n"
        f"- Primary store: {stack['database']}.\n"
        "- ACID transactions for cart/checkout/order integrity.\n"
        "- Explicit indexing for user, SKU, order lookup, and state transitions.\n\n"
        "## Integration Architecture\n"
        "- Payment provider adapter (authorize/capture/refund).\n"
        "- Shipment adapter (quote/create/tracking webhook).\n"
        "- Notification adapter (email + in-app).\n\n"
        "## Security Architecture\n"
        "- Session/JWT auth with RBAC + ownership checks.\n"
        "- Input validation at API boundary plus domain invariants.\n"
        "- Secrets via env/secret manager, never in repo.\n\n"
        "## Observability Architecture\n"
        "- Structured logs + audit logs + trace IDs/correlation IDs.\n"
        "- Metrics for technical SLIs and business KPIs.\n"
        "- Health/readiness checks and alert thresholds.\n\n"
        "## Deployment Architecture\n"
        "- Dockerized services behind reverse proxy.\n"
        "- Stateful persistence for Postgres volumes and backup strategy.\n"
        "- Migration job per release.\n\n"
        "## Scalability Considerations\n"
        "- Stateless API horizontal scaling.\n"
        "- Read-heavy catalog cache layer.\n"
        "- Async side effects for notifications/analytics.\n\n"
        "## Risks and Trade-offs\n"
        "- Monolith accelerates delivery but requires strict module boundaries.\n"
        "- Payment/shipping integrations are high-risk and require sandbox verification.\n"
    )


def _module_decomposition_md(modules: list[dict[str, str]]) -> str:
    lines = ["# Module Decomposition", ""]
    for module in modules:
        lines.extend(
            [
                f"## {module['name']}",
                f"- Responsibility: {module['responsibility']}",
                "- Inputs: HTTP commands, scheduled tasks, and domain events.",
                "- Outputs: response DTOs, persisted state changes, emitted events.",
                "- Dependencies: shared auth/logging/error packages only.",
                "- Business rules covered: module-specific invariants and lifecycle transitions.",
                f"- APIs owned: {module['apis']}",
                f"- Data owned: {module['data']}",
                "- Risks: coupling leaks, stale state transitions, integration retries.",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _bounded_contexts_md() -> str:
    return (
        "# Bounded Contexts\n\n"
        "## Identity\n"
        "- Purpose: Authentication, authorization, and session governance.\n"
        "- Aggregate roots: User, Session.\n"
        "- Invariants: unique email, active session constraints, role membership.\n"
        "- Events produced: user_registered, user_logged_in, session_expired.\n\n"
        "## Catalog\n"
        "- Purpose: Product lifecycle and inventory read model.\n"
        "- Aggregate roots: Product, Inventory.\n"
        "- Invariants: SKU uniqueness, non-negative stock, publish state validity.\n"
        "- Events produced: product_published, inventory_adjusted.\n\n"
        "## Checkout\n"
        "- Purpose: Cart to order conversion and payment orchestration.\n"
        "- Aggregate roots: Cart, Order, Payment.\n"
        "- Invariants: legal state transitions, amount reconciliation, idempotent checkout.\n"
        "- Events produced: checkout_requested, order_created, payment_failed.\n\n"
        "## Orders\n"
        "- Purpose: Post-purchase lifecycle and fulfillment coordination.\n"
        "- Aggregate roots: Order, Shipment.\n"
        "- Invariants: immutable paid order totals, cancellation/refund policy.\n"
        "- Events consumed: payment_captured.\n"
        "- Events produced: order_shipped, order_delivered.\n"
    )


def _api_contracts_md() -> str:
    return (
        "# API Contracts\n\n"
        "## Auth\n"
        "- `POST /api/auth/register`: creates user. 201 + `AuthResponse`.\n"
        "- `POST /api/auth/login`: authenticates user. 200 + `AuthResponse`.\n"
        "- `POST /api/auth/logout`: invalidates session. 204.\n\n"
        "## Catalog\n"
        "- `GET /api/products`: paginated list with filters and sorting.\n"
        "- `GET /api/products/{productId}`: product detail + stock projection.\n\n"
        "## Cart & Checkout\n"
        "- `GET /api/cart`: current cart.\n"
        "- `POST /api/cart/items`: add line item.\n"
        "- `PATCH /api/cart/items/{itemId}`: update quantity.\n"
        "- `DELETE /api/cart/items/{itemId}`: remove item.\n"
        "- `POST /api/checkout`: creates order and payment intent.\n\n"
        "## Orders\n"
        "- `GET /api/orders`: current user orders.\n"
        "- `GET /api/orders/{orderId}`: single order detail.\n\n"
        "## Profile/Admin\n"
        "- `GET /api/profile`, `PUT /api/profile`.\n"
        "- `POST /api/admin/products`, `PATCH /api/admin/products/{id}` (admin role).\n"
    )


def _openapi_yaml() -> str:
    return """openapi: 3.0.3
info:
  title: Ecommerce MVP API
  version: 0.2.0
servers:
  - url: http://localhost:8000
security:
  - bearerAuth: []
paths:
  /api/auth/register:
    post:
      summary: Register user
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RegisterRequest'
      responses:
        '201':
          description: Registered
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
        '409':
          $ref: '#/components/responses/Conflict'
        '422':
          $ref: '#/components/responses/ValidationError'
  /api/auth/login:
    post:
      summary: Login user
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/LoginRequest'
      responses:
        '200':
          description: Authenticated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '422':
          $ref: '#/components/responses/ValidationError'
  /api/products:
    get:
      summary: List products
      parameters:
        - in: query
          name: page
          schema: { type: integer, minimum: 1, default: 1 }
        - in: query
          name: page_size
          schema: { type: integer, minimum: 1, maximum: 100, default: 20 }
        - in: query
          name: q
          schema: { type: string }
      responses:
        '200':
          description: Product page
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProductListResponse'
  /api/cart/items:
    post:
      summary: Add item to cart
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/AddCartItemRequest'
      responses:
        '200':
          description: Updated cart
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CartResponse'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          $ref: '#/components/responses/ValidationError'
  /api/checkout:
    post:
      summary: Checkout cart
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CheckoutRequest'
      responses:
        '201':
          description: Order created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
        '409':
          $ref: '#/components/responses/Conflict'
        '422':
          $ref: '#/components/responses/ValidationError'
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  responses:
    ValidationError:
      description: Validation failed
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ValidationErrorResponse'
    Unauthorized:
      description: Unauthorized
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    Conflict:
      description: Business conflict
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
  schemas:
    RegisterRequest:
      type: object
      required: [email, password, full_name]
      properties:
        email: { type: string, format: email }
        password: { type: string, minLength: 10 }
        full_name: { type: string, minLength: 2 }
    LoginRequest:
      type: object
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string, minLength: 10 }
    AuthResponse:
      type: object
      required: [access_token, token_type, user]
      properties:
        access_token: { type: string }
        token_type: { type: string, example: bearer }
        user:
          $ref: '#/components/schemas/User'
    AddCartItemRequest:
      type: object
      required: [product_id, quantity]
      properties:
        product_id: { type: string, format: uuid }
        quantity: { type: integer, minimum: 1, maximum: 50 }
    CheckoutRequest:
      type: object
      required: [address_id, payment_method]
      properties:
        address_id: { type: string, format: uuid }
        payment_method: { type: string, enum: [card, transfer, cash_on_delivery] }
        idempotency_key: { type: string, minLength: 16 }
    Product:
      type: object
      required: [id, sku, title, price, currency]
      properties:
        id: { type: string, format: uuid }
        sku: { type: string }
        title: { type: string }
        description: { type: string }
        price: { type: number, format: float }
        currency: { type: string, minLength: 3, maxLength: 3 }
    ProductListResponse:
      type: object
      required: [items, page, page_size, total]
      properties:
        items:
          type: array
          items: { $ref: '#/components/schemas/Product' }
        page: { type: integer }
        page_size: { type: integer }
        total: { type: integer }
    CartResponse:
      type: object
      required: [id, status, items, subtotal, total]
      properties:
        id: { type: string, format: uuid }
        status: { type: string, enum: [ACTIVE, ABANDONED, CHECKED_OUT, EXPIRED] }
        items:
          type: array
          items: { $ref: '#/components/schemas/CartItem' }
        subtotal: { type: number, format: float }
        total: { type: number, format: float }
    CartItem:
      type: object
      required: [id, product_id, quantity, unit_price]
      properties:
        id: { type: string, format: uuid }
        product_id: { type: string, format: uuid }
        quantity: { type: integer, minimum: 1 }
        unit_price: { type: number, format: float }
    OrderResponse:
      type: object
      required: [order_id, status, amount_total, currency]
      properties:
        order_id: { type: string, format: uuid }
        status: { type: string, enum: [PENDING, PAID, FAILED, SHIPPED, DELIVERED, CANCELLED, REFUNDED] }
        amount_total: { type: number, format: float }
        currency: { type: string, minLength: 3, maxLength: 3 }
    User:
      type: object
      required: [id, email, role]
      properties:
        id: { type: string, format: uuid }
        email: { type: string, format: email }
        role: { type: string, enum: [customer, admin] }
    ValidationErrorResponse:
      type: object
      properties:
        code: { type: string, example: validation_error }
        errors:
          type: array
          items:
            type: object
            properties:
              field: { type: string }
              message: { type: string }
    ErrorResponse:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        correlation_id: { type: string }
"""


def _database_design_md() -> str:
    return (
        "# Database Design\n\n"
        "## Tables and Fields\n\n"
        "### users\n"
        "- `id UUID PK`\n- `email VARCHAR(255) UNIQUE NOT NULL`\n- `password_hash VARCHAR(255) NOT NULL`\n- `role VARCHAR(32) NOT NULL`\n- `status VARCHAR(32) NOT NULL DEFAULT 'active'`\n"
        "- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n- `deleted_at TIMESTAMP NULL`\n\n"
        "### products\n"
        "- `id UUID PK`\n- `sku VARCHAR(64) UNIQUE NOT NULL`\n- `title VARCHAR(255) NOT NULL`\n- `description TEXT`\n- `price NUMERIC(12,2) NOT NULL CHECK (price >= 0)`\n"
        "- `currency CHAR(3) NOT NULL`\n- `status VARCHAR(32) NOT NULL DEFAULT 'active'`\n- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### inventory\n"
        "- `product_id UUID PK FK -> products.id`\n- `available_qty INT NOT NULL CHECK (available_qty >= 0)`\n- `reserved_qty INT NOT NULL CHECK (reserved_qty >= 0)`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### carts\n"
        "- `id UUID PK`\n- `user_id UUID FK -> users.id`\n- `status VARCHAR(32) NOT NULL CHECK (status IN ('ACTIVE','ABANDONED','CHECKED_OUT','EXPIRED'))`\n"
        "- `currency CHAR(3) NOT NULL`\n- `expires_at TIMESTAMP NULL`\n- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### cart_items\n"
        "- `id UUID PK`\n- `cart_id UUID NOT NULL FK -> carts.id`\n- `product_id UUID NOT NULL FK -> products.id`\n- `quantity INT NOT NULL CHECK (quantity > 0)`\n"
        "- `unit_price NUMERIC(12,2) NOT NULL`\n- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### orders\n"
        "- `id UUID PK`\n- `user_id UUID NOT NULL FK -> users.id`\n- `cart_id UUID FK -> carts.id`\n- `status VARCHAR(32) NOT NULL`\n- `amount_subtotal NUMERIC(12,2) NOT NULL`\n"
        "- `amount_total NUMERIC(12,2) NOT NULL`\n- `currency CHAR(3) NOT NULL`\n- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### order_items\n"
        "- `id UUID PK`\n- `order_id UUID NOT NULL FK -> orders.id`\n- `product_id UUID NOT NULL FK -> products.id`\n- `quantity INT NOT NULL CHECK (quantity > 0)`\n"
        "- `unit_price NUMERIC(12,2) NOT NULL`\n\n"
        "### payments\n"
        "- `id UUID PK`\n- `order_id UUID NOT NULL FK -> orders.id`\n- `provider VARCHAR(64) NOT NULL`\n- `provider_ref VARCHAR(128)`\n- `status VARCHAR(32) NOT NULL`\n"
        "- `amount NUMERIC(12,2) NOT NULL`\n- `currency CHAR(3) NOT NULL`\n- `created_at TIMESTAMP NOT NULL`\n- `updated_at TIMESTAMP NOT NULL`\n\n"
        "### shipments\n"
        "- `id UUID PK`\n- `order_id UUID NOT NULL FK -> orders.id`\n- `carrier VARCHAR(64)`\n- `tracking_number VARCHAR(128)`\n- `status VARCHAR(32) NOT NULL`\n"
        "- `shipped_at TIMESTAMP NULL`\n- `delivered_at TIMESTAMP NULL`\n\n"
        "## Indexes\n"
        "- `idx_users_email` unique(email)\n"
        "- `idx_products_sku` unique(sku)\n"
        "- `idx_orders_user_status` (user_id, status)\n"
        "- `idx_cart_items_cart_product` unique(cart_id, product_id)\n"
        "- `idx_payments_order_status` (order_id, status)\n\n"
        "## Constraints and Lifecycle Rules\n"
        "- Order status transition guard: PENDING -> PAID/FAILED -> SHIPPED -> DELIVERED/CANCELLED/REFUNDED.\n"
        "- Cart can mutate only in ACTIVE state.\n"
        "- Inventory reservation must be released on checkout failure.\n\n"
        "## Soft Delete Strategy\n"
        "- `users.deleted_at` for account deactivation/audit preservation.\n"
        "- Products archived via status; physical delete only for compliance pipelines.\n"
    )


def _frontend_architecture_md() -> str:
    return (
        "# Frontend Architecture\n\n"
        "## Route Hierarchy\n"
        "- Public: `/`, `/about`, `/contact`, `/login`, `/register`, `/catalog`, `/products/:id`\n"
        "- Protected: `/dashboard`, `/profile`, `/settings`, `/orders`, `/cart`, `/checkout`\n"
        "- Admin: `/admin/products`, `/admin/orders`, `/admin/reports`\n\n"
        "## Layouts and Shared Components\n"
        "- `PublicLayout`: marketing header/footer and CTA blocks.\n"
        "- `AppLayout`: sidebar, topbar, breadcrumbs, notification center.\n"
        "- Shared: product card/list, pagination, form controls, toasts, skeleton loaders.\n\n"
        "## State and Data\n"
        "- API client with auth interceptor and correlation-id propagation.\n"
        "- React Query caches: products, cart, profile, orders.\n"
        "- Form state with Zod schema validation and error mapping.\n\n"
        "## UX Behavior\n"
        "- Loading, empty, retry and hard-error views for every critical page.\n"
        "- Session expiry redirect with intended route preservation.\n"
        "- Role-aware navigation rendering.\n"
    )


def _backend_architecture_md() -> str:
    return (
        "# Backend Architecture\n\n"
        "## Folder Structure\n"
        "```text\n"
        "backend/\n"
        "  src/\n"
        "    api/\n"
        "      routers/\n"
        "      middleware/\n"
        "      schemas/\n"
        "    application/\n"
        "      use_cases/\n"
        "      services/\n"
        "      dto/\n"
        "    domain/\n"
        "      entities/\n"
        "      value_objects/\n"
        "      repositories/\n"
        "      policies/\n"
        "    infrastructure/\n"
        "      persistence/\n"
        "      integrations/\n"
        "      messaging/\n"
        "    shared/\n"
        "      errors/\n"
        "      logging/\n"
        "      config/\n"
        "```\n\n"
        "## Layer Responsibilities\n"
        "- API layer: auth, request parsing, DTO validation, response mapping.\n"
        "- Application layer: orchestrates use cases and transactions.\n"
        "- Domain layer: invariants, state transitions, business rules.\n"
        "- Infrastructure layer: database repositories, provider adapters, queues.\n\n"
        "## Validation Strategy\n"
        "- Request DTO validation at API boundary.\n"
        "- Domain invariants enforced in entities/policies.\n"
        "- Integration payload validation before external calls.\n\n"
        "## Error Handling and Logging\n"
        "- Typed exception hierarchy (`ValidationError`, `BusinessRuleError`, `IntegrationError`).\n"
        "- HTTP error mapper to consistent JSON (`code`, `message`, `correlation_id`).\n"
        "- Structured logs include `trace_id`, `user_id`, `order_id` where available.\n\n"
        "## Auth and Security Middleware\n"
        "- JWT/session validation middleware.\n"
        "- RBAC + ownership checks at router/use-case boundary.\n"
        "- Rate limit middleware on auth and checkout endpoints.\n\n"
        "## Dependency Boundaries\n"
        "- API depends only on application contracts.\n"
        "- Domain has no dependency on frameworks or IO.\n"
        "- Infrastructure implements domain repository interfaces.\n"
    )


def _event_flow_md() -> str:
    return (
        "# Event/Flow Architecture\n\n"
        "## Core Events\n"
        "- `user_registered`\n- `cart_created`\n- `checkout_requested`\n- `order_created`\n- `payment_authorized`\n- `payment_failed`\n- `order_shipped`\n\n"
        "## Sync vs Async\n"
        "- Sync: auth, catalog reads, cart mutations, checkout command.\n"
        "- Async-ready: notifications, analytics, shipment updates.\n\n"
        "## Reliability Controls\n"
        "- Idempotency key on checkout and payment endpoints.\n"
        "- Retry policy for transient provider failures (exponential backoff).\n"
        "- Deduplication keys for async consumers.\n"
        "- Dead-letter strategy for irrecoverable integration events.\n"
    )


def _security_md() -> str:
    return (
        "# Security Architecture\n\n"
        "## Authentication and Authorization\n"
        "- Session/JWT with rotation and expiration.\n"
        "- RBAC roles: customer, admin.\n"
        "- Ownership checks for cart/order/profile resources.\n\n"
        "## Input Validation\n"
        "- DTO-level input validation for every mutating endpoint.\n"
        "- Domain-level business validation (stock, price, status transitions).\n\n"
        "## Data Protection\n"
        "- Password hashing with strong algorithm and salt.\n"
        "- Secrets in env/secret manager; never hardcoded.\n"
        "- Sensitive payload redaction in logs.\n\n"
        "## Abuse Protection\n"
        "- Rate limiting on auth and checkout.\n"
        "- CSRF/CORS hardening for session mode.\n"
        "- OWASP Top-10 review for release gates.\n"
    )


def _observability_md() -> str:
    return (
        "# Observability Plan\n\n"
        "## Logs\n"
        "- Technical logs: request lifecycle, DB/query timing, integration calls.\n"
        "- Audit logs: login/logout, role changes, order status transitions, admin actions.\n"
        "- Log fields: timestamp, level, service, route, user_id, correlation_id, trace_id.\n\n"
        "## Metrics\n"
        "- API: latency p95, error rate, throughput per route.\n"
        "- Infra: DB CPU, connection pool usage, queue lag.\n"
        "- Business KPIs: conversion rate, cart abandonment, payment failure rate.\n\n"
        "## Traces\n"
        "- Distributed traces across frontend -> API -> DB/provider adapters.\n"
        "- Trace checkout and auth critical paths with span tags for order_id/user_id.\n\n"
        "## Health Checks\n"
        "- `/health/live` liveness and `/health/ready` readiness.\n"
        "- Readiness verifies DB connectivity + migration version + dependency pings.\n\n"
        "## Alerts\n"
        "- p95 checkout latency > 2.5s for 10m.\n"
        "- payment failure rate > 5% for 15m.\n"
        "- 5xx error rate > 2% for 5m.\n"
    )


def _deployment_md() -> str:
    return (
        "# Deployment Architecture\n\n"
        "## Docker Services\n"
        "- `frontend`: React app served via Nginx.\n"
        "- `backend`: FastAPI app + workers.\n"
        "- `postgres`: primary datastore with persistent volume.\n"
        "- `redis` (optional): cache/session/rate limit backend.\n\n"
        "## Networking\n"
        "- Internal bridge network for service-to-service traffic.\n"
        "- Reverse proxy exposes frontend and routes API traffic.\n"
        "- Backend not directly public in production.\n\n"
        "## Environment Variables\n"
        "- `DATABASE_URL`, `AUTH_SECRET`, `JWT_TTL_SECONDS`, `REDIS_URL`.\n"
        "- `PAYMENT_PROVIDER_KEY`, `SHIPMENT_PROVIDER_KEY`.\n"
        "- `LOG_LEVEL`, `OTEL_EXPORTER_ENDPOINT`.\n\n"
        "## Persistence and Migrations\n"
        "- Postgres data persisted in named volume.\n"
        "- Alembic migration job runs before backend rollout.\n"
        "- Backward-compatible migration policy for zero-downtime releases.\n\n"
        "## Secrets Handling\n"
        "- Local: `.env` for development only.\n"
        "- Production: secret manager/KMS and runtime injection.\n"
    )


def _technical_risks_md() -> str:
    return (
        "# Technical Risks\n\n"
        "| Risk | Impact | Likelihood | Mitigation | Owner |\n|---|---|---|---|---|\n"
        "| Checkout race conditions | High | Medium | Idempotency + transactional locking around stock reservation | Architect/Developer |\n"
        "| Payment provider instability | High | Medium | Retry/backoff + reconciliation job + failure UX | Architect/QA |\n"
        "| Session expiration regression | Medium | Medium | Contract tests for route guards and refresh flows | Frontend/QA |\n"
        "| Migration drift | High | Low | CI migration verification + rollback plan | DevOps/Developer |\n"
    )


def _developer_handoff_md(stack: dict[str, str]) -> str:
    return (
        "# Developer Handoff\n\n"
        f"## Stack Assumptions\n- Frontend: {stack['frontend']}\n- Backend: {stack['backend']}\n- Database: {stack['database']}\n\n"
        "## Implementation Order\n"
        "1. Auth + profile foundation (entities, DTOs, middleware, routes).\n"
        "2. Catalog + inventory read APIs and UI catalog/detail pages.\n"
        "3. Cart APIs + cart UI state/actions.\n"
        "4. Checkout/order creation + payment adapter + order history.\n"
        "5. Observability, error handling hardening, and regression tests.\n\n"
        "## Backend File Targets\n"
        "- `src/api/routers/auth.py`, `products.py`, `cart.py`, `checkout.py`, `orders.py`, `profile.py`\n"
        "- `src/application/use_cases/*`\n"
        "- `src/application/dto/*`\n"
        "- `src/domain/entities/*`, `policies/*`, `repositories/*`\n"
        "- `src/infrastructure/persistence/repositories/*`\n"
        "- `src/infrastructure/integrations/payment_adapter.py`, `shipment_adapter.py`\n\n"
        "## Frontend File Targets\n"
        "- `src/routes/public/*`, `src/routes/app/*`, `src/routes/admin/*`\n"
        "- `src/components/layout/*`, `catalog/*`, `cart/*`, `checkout/*`\n"
        "- `src/lib/api-client.ts`, `src/lib/query-client.ts`, `src/lib/auth.ts`\n\n"
        "## Required Endpoints and DTOs\n"
        "- Auth: register/login/logout DTOs + validation errors.\n"
        "- Products: list/detail filters and pagination DTOs.\n"
        "- Cart: add/update/remove items DTOs.\n"
        "- Checkout: request DTO with idempotency key, response with order state.\n"
        "- Orders: summary/detail responses.\n\n"
        "## Validation Rules and Non-Negotiables\n"
        "- Enforce stock >= requested quantity before checkout.\n"
        "- Enforce legal status transitions for cart/order/payment.\n"
        "- Never process checkout without authenticated user (unless guest explicitly enabled).\n\n"
        "## Tests Expected\n"
        "- Unit: domain state transitions and validations.\n"
        "- Integration: auth, catalog filters, cart mutations, checkout and payment failure flows.\n"
        "- E2E smoke: register/login -> browse -> add cart -> checkout -> order history.\n"
    )


def _quality_report_md() -> str:
    return (
        "# Architect Quality Report\n\n"
        "Scoring is finalized by runtime depth evaluator after artifact completion and repairs.\n"
    )


def _adr_docs() -> dict[str, str]:
    return {
        "adr/0001-architecture-style.md": "# ADR 0001 - Architecture Style\n\nContext: need MVP speed with future scale path.\nDecision: modular monolith with clean module boundaries.\nConsequences: faster delivery, governance discipline required.\nAlternatives: microservices-first.\n",
        "adr/0002-auth-session-strategy.md": "# ADR 0002 - Auth Session Strategy\n\nContext: secure customer and admin access.\nDecision: JWT/session with RBAC and ownership checks.\nConsequences: middleware complexity, stronger security baseline.\nAlternatives: API key-only model.\n",
        "adr/0003-database-design.md": "# ADR 0003 - Database Design\n\nContext: transactional checkout correctness.\nDecision: relational model with strict constraints and status transitions.\nConsequences: migration/versioning discipline required.\nAlternatives: document database.\n",
        "adr/0004-frontend-routing.md": "# ADR 0004 - Frontend Routing\n\nContext: public/auth/admin route separation.\nDecision: split layouts with guard middleware and role-aware nav.\nConsequences: clearer UX and security, added routing setup.\nAlternatives: flat route tree.\n",
        "adr/0005-error-handling.md": "# ADR 0005 - Error Handling\n\nContext: predictable API and UX failures.\nDecision: centralized typed errors and standard error payload schema.\nConsequences: upfront contract design, easier QA automation.\nAlternatives: ad hoc endpoint-specific errors.\n",
    }


def _diagram_bundle() -> dict[str, str]:
    return {
        "diagrams/system_context.mmd": "flowchart LR\nUser-->Frontend\nAdmin-->Frontend\nFrontend-->Backend\nBackend-->DB\nBackend-->Payment\nBackend-->Shipment\nBackend-->Notifications\n",
        "diagrams/container_diagram.mmd": "flowchart TD\nBrowser-->Nginx\nNginx-->WebApp\nNginx-->API\nAPI-->Postgres\nAPI-->Redis\nAPI-->PaymentProvider\nAPI-->ShipmentProvider\n",
        "diagrams/module_dependencies.mmd": "flowchart LR\nIdentity-->Cart\nCatalog-->Cart\nCart-->Checkout\nCheckout-->Orders\nOrders-->Notifications\nAdmin-->Catalog\n",
        "diagrams/entity_relationships.mmd": "erDiagram\nUSERS ||--o{ CARTS : owns\nUSERS ||--o{ ORDERS : places\nPRODUCTS ||--o{ INVENTORY : has\nCARTS ||--|{ CART_ITEMS : contains\nORDERS ||--|{ ORDER_ITEMS : contains\nORDERS ||--o{ PAYMENTS : has\nORDERS ||--o{ SHIPMENTS : has\n",
        "diagrams/checkout_sequence.mmd": "sequenceDiagram\nparticipant U as User\nparticipant FE as Frontend\nparticipant BE as Backend\nparticipant DB as PostgreSQL\nparticipant P as Payment\nU->>FE: Confirm checkout\nFE->>BE: POST /api/checkout\nBE->>DB: Validate cart + reserve stock\nBE->>P: Authorize payment\nP-->>BE: Result\nBE->>DB: Create order + payment record\nBE-->>FE: Order response\n",
        "diagrams/auth_sequence.mmd": "sequenceDiagram\nparticipant U as User\nparticipant FE as Frontend\nparticipant BE as Backend\nparticipant DB as PostgreSQL\nU->>FE: Login\nFE->>BE: POST /api/auth/login\nBE->>DB: Validate credentials\nBE-->>FE: access token + user profile\n",
        "diagrams/deployment_diagram.mmd": "flowchart LR\nClient-->Ingress\nIngress-->Frontend\nIngress-->Backend\nBackend-->Postgres[(Postgres Volume)]\nBackend-->Redis[(Redis)]\nBackend-->ExternalPayment\nBackend-->ExternalShipment\n",
    }

