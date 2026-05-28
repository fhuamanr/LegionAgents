from core.agents.architect_intelligence import build_architect_bundle


def test_architect_bundle_generates_required_blueprint_documents() -> None:
    bundle = build_architect_bundle(
        task="Use finalized BA output for an e-commerce platform with checkout.",
        ba_index={
            "pages": {"home": True, "dashboard": True, "profile": True, "settings": True},
            "entities": ["User", "Product", "Order"],
        },
        ba_docs={
            "application_shell.md": "Public + protected routes",
            "domain_entities.md": "User, Product, Cart, Order",
            "api_expectations.md": "Auth, products, cart, checkout endpoints",
        },
        structured_output={"summary": "Architect output"},
    )
    docs = bundle["docs"]
    assert "architecture.md" in docs
    assert "module_decomposition.md" in docs
    assert "bounded_contexts.md" in docs
    assert "api_contracts.md" in docs
    assert "openapi_draft.yaml" in docs
    assert "database_design.md" in docs
    assert "frontend_architecture.md" in docs
    assert "backend_architecture.md" in docs
    assert "event_flow_architecture.md" in docs
    assert "security_architecture.md" in docs
    assert "observability_plan.md" in docs
    assert "deployment_architecture.md" in docs
    assert "technical_risks.md" in docs
    assert "developer_handoff.md" in docs
    assert "architect_quality_report.md" in docs
    assert "adr/0001-architecture-style.md" in docs
    assert "adr/0005-error-handling.md" in docs


def test_architect_bundle_generates_required_diagrams() -> None:
    bundle = build_architect_bundle(
        task="Architecture for ecommerce checkout",
        ba_index={},
        ba_docs={},
        structured_output={},
    )
    diagrams = bundle["diagrams"]
    assert "diagrams/system_context.mmd" in diagrams
    assert "diagrams/container_diagram.mmd" in diagrams
    assert "diagrams/module_dependencies.mmd" in diagrams
    assert "diagrams/entity_relationships.mmd" in diagrams
    assert "diagrams/checkout_sequence.mmd" in diagrams
    assert "diagrams/auth_sequence.mmd" in diagrams
    assert "diagrams/deployment_diagram.mmd" in diagrams


def test_architect_bundle_openapi_and_backend_depth() -> None:
    bundle = build_architect_bundle(
        task="Architecture for ecommerce checkout",
        ba_index={},
        ba_docs={},
        structured_output={},
    )
    docs = bundle["docs"]
    openapi = docs["openapi_draft.yaml"].lower()
    backend = docs["backend_architecture.md"].lower()
    database = docs["database_design.md"].lower()
    observability = docs["observability_plan.md"].lower()
    deployment = docs["deployment_architecture.md"].lower()
    handoff = docs["developer_handoff.md"].lower()
    assert "components:" in openapi
    assert "schemas:" in openapi
    assert "requestbody" in openapi
    assert "responses:" in openapi
    assert "api/" in backend or "api layer" in backend
    assert "application" in backend and "domain" in backend and "infrastructure" in backend
    assert "primary key" in database or "pk" in database
    assert "foreign key" in database or "fk" in database
    assert "metrics" in observability and "traces" in observability and "correlation" in observability
    assert "docker" in deployment and "migration" in deployment and "secrets" in deployment
    assert "implementation order" in handoff and "endpoints" in handoff and "tests expected" in handoff
