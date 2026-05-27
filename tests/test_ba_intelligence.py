from core.agents.ba_intelligence import build_ba_intelligence_bundle


def test_ba_generates_clarification_questions_for_ambiguous_input() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={"summary": "MVP ecommerce"},
    )
    questions = bundle["clarification_questions"]
    assert questions
    assert any("payment" in item["question"].lower() for item in questions)


def test_ba_detects_missing_requirements_and_integrations() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Build ecommerce checkout",
        structured_output={},
    )
    gaps = bundle["gaps"]
    assert any("payment" in gap.lower() for gap in gaps)
    assert any("shipping" in gap.lower() for gap in gaps)
    integrations = bundle["integrations"]
    assert integrations


def test_ba_generates_richer_acceptance_criteria_and_edge_cases() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Build ecommerce checkout with payment and shipping",
        structured_output={"user_stories": []},
    )
    docs = bundle["documents"]
    acceptance = docs["acceptance_criteria.md"].lower()
    edge_cases = docs["edge_cases.md"].lower()
    assert "given" in acceptance
    assert "checkout" in acceptance
    assert "edge" in edge_cases
    assert "out-of-stock" in edge_cases or "concurrent" in edge_cases


def test_ba_generates_flow_diagrams() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Build ecommerce platform for customer and admin",
        structured_output={},
    )
    diagrams = bundle["diagrams"]
    assert "diagrams/functional_flow.mmd" in diagrams
    assert "flowchart" in diagrams["diagrams/functional_flow.mmd"].lower()


def test_ba_generates_domain_entities_state_machines_and_events() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={},
    )
    docs = bundle["documents"]
    assert "domain_entities.md" in docs
    assert "state_machines.md" in docs
    assert "business_events.md" in docs
    assert "order" in docs["domain_entities.md"].lower()
    assert "cart" in docs["state_machines.md"].lower()
    assert "payment_failed" in docs["business_events.md"].lower()


def test_ba_generates_validation_permissions_and_failure_flows() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={},
    )
    docs = bundle["documents"]
    assert "validation_rules.md" in docs
    assert "permissions_matrix.md" in docs
    assert "failure_flows.md" in docs
    assert "password" in docs["validation_rules.md"].lower()
    assert "admin" in docs["permissions_matrix.md"].lower()
    assert "payment failure" in docs["failure_flows.md"].lower()


def test_ba_infers_mvp_website_navigation_and_dashboard_baseline() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={},
    )
    mvp = bundle["inferred_mvp_structure"]
    assert any("home" in page.lower() for page in mvp["public_pages"])
    assert any("dashboard" in page.lower() for page in mvp["authenticated_pages"])
    assert any("profile" in page.lower() for page in mvp["authenticated_pages"])
    assert any("settings" in page.lower() for page in mvp["authenticated_pages"])
    assert "mvp_application_flow.md" in bundle["documents"]
    assert "frontend_mvp_expectations.md" in bundle["documents"]


def test_ba_consistency_and_quality_report_generated() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={"user_stories": []},
    )
    assert "consistency" in bundle
    assert "quality_report" in bundle
    assert "ba_quality_report.md" in bundle["documents"]
    assert "completeness score" in bundle["documents"]["ba_quality_report.md"].lower()


def test_ba_generates_application_shell_navigation_and_lifecycle_artifacts() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={},
    )
    docs = bundle["documents"]
    assert "application_shell.md" in docs
    assert "navigation_structure.md" in docs
    assert "user_lifecycle.md" in docs
    assert "routing hierarchy" in docs["application_shell.md"].lower()
    assert "public navigation" in docs["navigation_structure.md"].lower()
    assert "session lifecycle" in docs["user_lifecycle.md"].lower()


def test_ba_generates_mvp_page_matrix_data_ownership_and_roadmap() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Generate an e-commerce platform with checkout.",
        structured_output={},
    )
    docs = bundle["documents"]
    assert "mvp_page_matrix.md" in docs
    assert "data_ownership.md" in docs
    assert "roadmap_priorities.md" in docs
    matrix = docs["mvp_page_matrix.md"].lower()
    assert "core mvp" in matrix
    assert "future enhancement" in matrix
    ownership = docs["data_ownership.md"].lower()
    assert "source of truth" in ownership
    roadmap = docs["roadmap_priorities.md"].lower()
    assert "mandatory mvp" in roadmap


def test_ba_infers_home_dashboard_profile_settings() -> None:
    bundle = build_ba_intelligence_bundle(
        task="Create web app with login + products + checkout",
        structured_output={},
    )
    core = [page.lower() for page in bundle["inferred_mvp_structure"]["core_mvp"]]
    assert any("home" in page for page in core)
    assert any("dashboard" in page for page in core)
    assert any("profile" in page for page in core)
    assert any("settings" in page for page in core)
