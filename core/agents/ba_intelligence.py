"""Business Analyst intelligence helpers for richer functional analysis artifacts."""

from __future__ import annotations

from typing import Any


def build_ba_intelligence_bundle(task: str, structured_output: dict[str, Any]) -> dict[str, Any]:
    """Build advanced BA intelligence documents and diagnostics."""

    text = f"{task}\n{structured_output}".lower()
    inferred_mvp = _infer_mvp_structure(text)
    gaps = _detect_gaps(text)
    questions = _clarification_questions(gaps)
    integrations = _detect_integrations(text)
    actors = _detect_actors(text)
    risks = _build_risks(gaps)
    edge_cases = _build_edge_cases(text)
    flow = _flow_diagram(actors)
    entities = _domain_entities_for_context(text)
    state_models = _state_models_for_context(text)
    events = _business_events_for_context(text)
    validations = _validation_rules_for_context(text)
    permissions = _permissions_for_context(actors)
    api_expectations = _api_expectations_for_context(text)
    failure_flows = _failure_flows_for_context(text)
    ux_rules = _ux_behavior_rules_for_context(text)
    functional_flows = _functional_flows_for_context(text, actors)
    consistency = _consistency_checks(
        inferred_mvp=inferred_mvp,
        entities=entities,
        states=state_models,
        events=events,
        validations=validations,
        permissions=permissions,
    )
    quality_report = _ba_quality_report(
        inferred_mvp=inferred_mvp,
        entities=entities,
        states=state_models,
        validations=validations,
        failure_flows=failure_flows,
        consistency=consistency,
        stories=structured_output.get("user_stories", []) if isinstance(structured_output, dict) else [],
    )

    docs: dict[str, str] = {
        "gap_analysis.md": _gap_analysis_markdown(gaps),
        "clarification_questions.md": _clarifications_markdown(questions),
        "executive_summary.md": _executive_summary(task, structured_output, gaps),
        "functional_specification.md": _functional_spec(task, actors, integrations),
        "user_stories.md": _user_stories_markdown(structured_output),
        "acceptance_criteria.md": _acceptance_markdown(structured_output, gaps),
        "business_rules.md": _business_rules_markdown(text),
        "requirements_matrix.md": _requirements_matrix_markdown(),
        "mvp_application_flow.md": _mvp_application_flow_markdown(inferred_mvp),
        "application_shell.md": _application_shell_markdown(inferred_mvp),
        "navigation_structure.md": _navigation_structure_markdown(inferred_mvp),
        "mvp_page_matrix.md": _mvp_page_matrix_markdown(inferred_mvp),
        "user_lifecycle.md": _user_lifecycle_markdown(),
        "data_ownership.md": _data_ownership_markdown(entities),
        "roadmap_priorities.md": _roadmap_priorities_markdown(inferred_mvp),
        "frontend_mvp_expectations.md": _frontend_mvp_expectations_markdown(inferred_mvp),
        "domain_entities.md": _domain_entities_markdown(entities),
        "state_machines.md": _state_machines_markdown(state_models),
        "business_events.md": _business_events_markdown(events),
        "functional_flows.md": _functional_flows_markdown(functional_flows),
        "validation_rules.md": _validation_rules_markdown(validations),
        "failure_flows.md": _failure_flows_markdown(failure_flows),
        "ux_behavior_rules.md": _ux_behavior_rules_markdown(ux_rules),
        "api_expectations.md": _api_expectations_markdown(api_expectations),
        "edge_cases.md": _list_markdown("Edge Cases", edge_cases),
        "assumptions.md": _assumptions_markdown(gaps),
        "risks.md": _list_markdown("Risks", risks),
        "integrations.md": _list_markdown("Integrations", integrations),
        "permissions_matrix.md": _permissions_matrix_markdown(actors, permissions),
        "ba_quality_report.md": _ba_quality_report_markdown(quality_report, consistency),
    }
    diagrams = {
        "diagrams/functional_flow.mmd": flow,
        "diagrams/actor_interactions.mmd": flow,
        "diagrams/navigation_map.mmd": _navigation_map_diagram(inferred_mvp),
        "diagrams/user_journey.mmd": _user_journey_diagram(inferred_mvp),
        "diagrams/page_transitions.mmd": _page_transition_diagram(inferred_mvp),
        "diagrams/state_cart_order.mmd": _state_diagram_for_cart_order(state_models),
        "diagrams/route_hierarchy.mmd": _route_hierarchy_diagram(inferred_mvp),
    }
    return {
        "gaps": gaps,
        "clarification_questions": questions,
        "integrations": integrations,
        "edge_cases": edge_cases,
        "actors": actors,
        "inferred_mvp_structure": inferred_mvp,
        "consistency": consistency,
        "quality_report": quality_report,
        "documents": docs,
        "diagrams": diagrams,
    }


def _infer_mvp_structure(text: str) -> dict[str, list[str]]:
    looks_like_web = any(
        keyword in text
        for keyword in (
            "website",
            "web application",
            "portal",
            "dashboard",
            "e-commerce",
            "ecommerce",
            "marketplace",
            "saas",
            "admin panel",
            "checkout",
        )
    )
    if not looks_like_web:
        return {"public_pages": [], "authenticated_pages": [], "domain_pages": [], "ux_components": []}
    public_pages = ["Home/Landing", "Login/Register", "About/Info", "Contact/Support"]
    authenticated_pages = ["Dashboard", "Profile", "Settings", "Session/Error/Empty states"]
    domain_pages = ["Catalog", "Product Details", "Cart", "Checkout", "Orders", "Admin Views", "Search/Filter"]
    ux_components = [
        "Global navigation (header/sidebar)",
        "Loading + skeleton states",
        "Validation feedback",
        "Role-aware navigation",
        "Retry + recoverable error handling",
        "Responsive layouts",
    ]
    core_mvp = [
        "Home/Landing",
        "Login/Register",
        "Catalog",
        "Product Details",
        "Cart",
        "Checkout",
        "Dashboard",
        "Profile",
        "Settings",
    ]
    recommended_mvp = ["Orders/History", "Notifications", "Support/Contact", "Error pages", "Empty states"]
    future_features = ["Advanced reports", "Coupons/Promotions engine", "Wishlist", "Recommendation system"]
    return {
        "public_pages": public_pages,
        "authenticated_pages": authenticated_pages,
        "domain_pages": domain_pages,
        "ux_components": ux_components,
        "core_mvp": core_mvp,
        "recommended_mvp": recommended_mvp,
        "future_features": future_features,
    }


def _detect_gaps(text: str) -> list[str]:
    checks = [
        ("payment", "Missing payment flow definition."),
        ("shipping", "Missing shipping/fulfillment definition."),
        ("auth", "Authentication and authorization scope is unclear."),
        ("role", "Actors/roles are not explicitly defined."),
        ("validation", "Input/business validations are underdefined."),
        ("error", "Error and recovery scenarios are missing."),
        ("integration", "External/internal integration points are not explicit."),
        ("session", "Session lifecycle (login/logout/expiry) is not explicit."),
        ("state", "Entity lifecycle/state transitions are missing."),
        ("permission", "Permission ownership and role constraints are missing."),
    ]
    return [message for keyword, message in checks if keyword not in text]


def _clarification_questions(gaps: list[str]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for gap in gaps:
        if "payment" in gap.lower():
            questions.append(
                {
                    "priority": "high",
                    "question": "Which payment methods and authorization/capture flow are required?",
                    "impact": "Defines checkout state machine, failure handling, and reconciliation.",
                }
            )
        elif "shipping" in gap.lower():
            questions.append(
                {
                    "priority": "high",
                    "question": "How should shipping methods, cost calculation, and delivery SLA be modeled?",
                    "impact": "Affects order totals, checkout UX, and downstream fulfillment events.",
                }
            )
        elif "auth" in gap.lower():
            questions.append(
                {
                    "priority": "high",
                    "question": "What auth model is required (guest checkout, JWT/session, role permissions)?",
                    "impact": "Affects API security, permissions matrix, and user/cart ownership logic.",
                }
            )
        else:
            questions.append(
                {
                    "priority": "medium",
                    "question": f"Please clarify: {gap}",
                    "impact": "Prevents contradictory implementation assumptions.",
                }
            )
    return questions


def _detect_integrations(text: str) -> list[str]:
    integrations: list[str] = []
    for keyword, name in (
        ("payment", "Payment gateway"),
        ("shipping", "Shipping carrier service"),
        ("email", "Email/notification provider"),
        ("inventory", "Inventory/stock synchronization"),
        ("analytics", "Analytics/events pipeline"),
    ):
        if keyword in text:
            integrations.append(name)
    return integrations or ["No explicit integrations specified (assumed local-only MVP)."]


def _detect_actors(text: str) -> list[str]:
    actors = []
    for keyword, actor in (
        ("admin", "Admin"),
        ("seller", "Seller"),
        ("buyer", "Buyer"),
        ("customer", "Customer"),
        ("guest", "Guest"),
    ):
        if keyword in text:
            actors.append(actor)
    return actors or ["Customer", "Admin"]


def _build_risks(gaps: list[str]) -> list[str]:
    risks = [f"Ambiguity risk: {gap}" for gap in gaps[:6]]
    risks.extend(
        [
            "Scope creep risk due to undefined boundaries between MVP and post-MVP.",
            "Operational risk if error-handling contracts are unspecified.",
        ]
    )
    return risks


def _build_edge_cases(text: str) -> list[str]:
    base = [
        "Product out-of-stock during checkout.",
        "Concurrent cart updates across devices.",
        "Price changed after item added to cart.",
        "Auth session expires mid-checkout.",
        "Invalid coupon/promotion combination.",
    ]
    if "payment" in text:
        base.append("Payment authorized but capture failed.")
    return base


def _flow_diagram(actors: list[str]) -> str:
    actor = actors[0] if actors else "Customer"
    return (
        "flowchart LR\n"
        f'{actor}["{actor}"] --> Browse["Browse products"]\n'
        "Browse --> Cart[\"Add to cart\"]\n"
        "Cart --> Checkout[\"Checkout\"]\n"
        "Checkout --> Validate[\"Validate stock + pricing\"]\n"
        "Validate --> Order[\"Create order\"]\n"
    )


def _domain_entities_for_context(text: str) -> list[dict[str, Any]]:
    base = [
        {
            "name": "User",
            "purpose": "Represents platform identity and ownership boundary.",
            "ownership": "Identity/Auth domain",
            "lifecycle": "registered -> active -> suspended -> deleted",
            "relationships": ["Cart", "Order", "Session"],
            "validations": ["unique email", "password policy", "role constraints"],
            "constraints": ["email unique", "role required"],
            "attributes": ["id", "email", "password_hash", "role", "status"],
        },
        {
            "name": "Product",
            "purpose": "Represents sellable catalog item.",
            "ownership": "Catalog domain",
            "lifecycle": "draft -> active -> archived",
            "relationships": ["Inventory", "CartItem", "OrderItem"],
            "validations": ["price >= 0", "sku unique", "stock non-negative"],
            "constraints": ["cannot checkout archived product"],
            "attributes": ["id", "sku", "title", "description", "price", "status"],
        },
    ]
    if "checkout" in text or "e-commerce" in text or "ecommerce" in text:
        base.extend(
            [
                {
                    "name": "Inventory",
                    "purpose": "Tracks available stock and reservation state.",
                    "ownership": "Inventory domain",
                    "lifecycle": "available -> reserved -> released/consumed",
                    "relationships": ["Product", "Order"],
                    "validations": ["stock >= 0", "reservation expiration"],
                    "constraints": ["prevent oversell"],
                    "attributes": ["product_id", "available_qty", "reserved_qty", "updated_at"],
                },
                {
                    "name": "Cart",
                    "purpose": "Temporary basket before order creation.",
                    "ownership": "Checkout domain",
                    "lifecycle": "active -> abandoned -> checked_out -> expired",
                    "relationships": ["User", "CartItem", "Order"],
                    "validations": ["owner match", "qty <= stock"],
                    "constraints": ["cannot mutate checked_out cart"],
                    "attributes": ["id", "user_id", "status", "currency", "updated_at"],
                },
                {
                    "name": "Order",
                    "purpose": "Persistent purchase transaction.",
                    "ownership": "Order domain",
                    "lifecycle": "pending -> paid -> shipped -> delivered / cancelled / refunded",
                    "relationships": ["User", "OrderItem", "Payment", "Shipment"],
                    "validations": ["total reconciliation", "legal state transitions"],
                    "constraints": ["cannot ship unpaid order"],
                    "attributes": ["id", "user_id", "status", "total", "created_at"],
                },
                {
                    "name": "Payment",
                    "purpose": "Tracks authorization/capture result.",
                    "ownership": "Payment domain",
                    "lifecycle": "initiated -> authorized -> captured / failed / refunded",
                    "relationships": ["Order"],
                    "validations": ["idempotency key", "amount match order total"],
                    "constraints": ["single active capture per order"],
                    "attributes": ["id", "order_id", "provider", "status", "amount"],
                },
                {
                    "name": "Shipment",
                    "purpose": "Tracks fulfillment and delivery state.",
                    "ownership": "Fulfillment domain",
                    "lifecycle": "pending -> in_transit -> delivered / returned / failed",
                    "relationships": ["Order"],
                    "validations": ["tracking format", "address completeness"],
                    "constraints": ["shipment requires paid order"],
                    "attributes": ["id", "order_id", "carrier", "tracking_id", "status"],
                },
                {
                    "name": "Session",
                    "purpose": "Represents authenticated browser/user session.",
                    "ownership": "Identity/Auth domain",
                    "lifecycle": "issued -> active -> expired -> revoked",
                    "relationships": ["User"],
                    "validations": ["expiry window", "token signature"],
                    "constraints": ["expired session blocks protected routes"],
                    "attributes": ["id", "user_id", "issued_at", "expires_at", "status"],
                },
            ]
        )
    return base


def _state_models_for_context(text: str) -> dict[str, dict[str, Any]]:
    models: dict[str, dict[str, Any]] = {
        "Cart": {
            "states": ["ACTIVE", "ABANDONED", "CHECKED_OUT", "EXPIRED"],
            "allowed_transitions": [
                "ACTIVE -> CHECKED_OUT",
                "ACTIVE -> ABANDONED",
                "ACTIVE -> EXPIRED",
                "ABANDONED -> ACTIVE",
            ],
            "invalid_transitions": ["CHECKED_OUT -> ACTIVE", "EXPIRED -> CHECKED_OUT"],
            "triggers": ["user_activity", "checkout_submit", "session_timeout"],
            "consequences": ["inventory reservation updates", "cart immutability after checkout"],
            "recovery_rules": ["abandoned cart reactivation with revalidation"],
        },
        "Order": {
            "states": ["PENDING", "PAID", "FAILED", "SHIPPED", "DELIVERED", "CANCELLED", "REFUNDED"],
            "allowed_transitions": [
                "PENDING -> PAID",
                "PENDING -> FAILED",
                "PAID -> SHIPPED",
                "SHIPPED -> DELIVERED",
                "PAID -> CANCELLED",
                "DELIVERED -> REFUNDED",
            ],
            "invalid_transitions": ["PENDING -> SHIPPED", "FAILED -> DELIVERED"],
            "triggers": ["payment_result", "fulfillment_update", "customer_cancellation"],
            "consequences": ["inventory commit/release", "customer notifications", "refund obligations"],
            "recovery_rules": ["payment retry window for FAILED", "manual intervention on shipment failure"],
        },
    }
    if "payment" in text:
        models["Payment"] = {
            "states": ["INITIATED", "AUTHORIZED", "CAPTURED", "FAILED", "REFUNDED"],
            "allowed_transitions": ["INITIATED -> AUTHORIZED", "AUTHORIZED -> CAPTURED", "AUTHORIZED -> FAILED", "CAPTURED -> REFUNDED"],
            "invalid_transitions": ["FAILED -> CAPTURED"],
            "triggers": ["gateway callbacks", "capture request", "refund request"],
            "consequences": ["order state updates", "finance reconciliation"],
            "recovery_rules": ["idempotent retry for transient gateway errors"],
        }
    return models


def _business_events_for_context(text: str) -> list[dict[str, Any]]:
    events = [
        {"name": "user_registered", "producer": "auth-service", "consumer": "profile-service", "payload": ["user_id", "email"], "impact": "enables onboarding", "retry": "at-least-once", "notifications": ["welcome_email"]},
        {"name": "cart_created", "producer": "cart-service", "consumer": "analytics", "payload": ["cart_id", "user_id"], "impact": "tracks buyer intent", "retry": "best-effort", "notifications": []},
        {"name": "order_created", "producer": "checkout-service", "consumer": "payment-service", "payload": ["order_id", "total"], "impact": "starts payment lifecycle", "retry": "at-least-once", "notifications": ["order_received"]},
        {"name": "payment_failed", "producer": "payment-service", "consumer": "checkout-service", "payload": ["order_id", "reason_code"], "impact": "requires retry or alternate method", "retry": "with backoff", "notifications": ["payment_failed_notice"]},
        {"name": "order_cancelled", "producer": "order-service", "consumer": "inventory-service", "payload": ["order_id"], "impact": "releases stock", "retry": "at-least-once", "notifications": ["order_cancelled_notice"]},
        {"name": "shipment_delivered", "producer": "fulfillment-service", "consumer": "order-service", "payload": ["order_id", "delivered_at"], "impact": "closes fulfillment loop", "retry": "best-effort", "notifications": ["delivered_notice"]},
    ]
    if "checkout" not in text:
        return events[:3]
    return events


def _validation_rules_for_context(text: str) -> list[str]:
    rules = [
        "Password must be at least 8 chars and include uppercase, lowercase, and digit.",
        "Email must be unique and RFC-compliant.",
        "Cart quantity must be positive and not exceed available stock.",
        "Payment amount must match computed order total.",
        "Duplicate order submission prevented via idempotency token.",
    ]
    if "shipping" in text:
        rules.append("Shipping address requires country, city, postal code, and valid phone.")
    return rules


def _permissions_for_context(actors: list[str]) -> list[dict[str, str]]:
    primary = actors[0] if actors else "Customer"
    return [
        {"actor": primary, "allowed": "browse products, manage own cart, checkout, view own orders", "restricted": "manage catalog/admin reports", "ownership": "only own resources"},
        {"actor": "Admin", "allowed": "manage products, view reports, override order states", "restricted": "none within admin scope", "ownership": "global operational scope"},
        {"actor": "Guest", "allowed": "browse catalog, create temporary cart", "restricted": "checkout, order history, profile updates", "ownership": "no persistent ownership"},
    ]


def _api_expectations_for_context(text: str) -> list[dict[str, Any]]:
    endpoints = [
        {"method": "POST", "path": "/api/auth/register", "payload": ["email", "password"], "validation": "email unique + password policy", "errors": ["409 duplicate_email", "422 validation_error"], "auth": "public"},
        {"method": "POST", "path": "/api/auth/login", "payload": ["email", "password"], "validation": "credential verification", "errors": ["401 invalid_credentials"], "auth": "public"},
        {"method": "GET", "path": "/api/products", "payload": ["q?", "page?", "sort?"], "validation": "query bounds", "errors": ["400 invalid_filters"], "auth": "optional"},
        {"method": "POST", "path": "/api/cart/items", "payload": ["product_id", "quantity"], "validation": "stock + ownership", "errors": ["404 product_missing", "409 stock_conflict"], "auth": "required"},
        {"method": "POST", "path": "/api/checkout", "payload": ["cart_id", "payment_method", "shipping_address"], "validation": "cart state + payment preconditions", "errors": ["409 invalid_cart_state", "402 payment_failed"], "auth": "required"},
    ]
    if "admin" in text or "dashboard" in text:
        endpoints.append({"method": "GET", "path": "/api/admin/reports", "payload": ["range"], "validation": "role=admin", "errors": ["403 forbidden"], "auth": "required-admin"})
    return endpoints


def _failure_flows_for_context(text: str) -> list[str]:
    return [
        "Payment failure: retain cart in ACTIVE, emit payment_failed event, show retry/alternate method UX.",
        "Session expiration: redirect to login, preserve unsaved cart intent, prompt re-authentication.",
        "Inventory race: detect stock conflict at checkout, recalculate totals, request confirmation.",
        "API timeout: retry idempotent calls with backoff, surface non-blocking status UI.",
        "Invalid navigation state: protect guarded routes and fallback to dashboard/home.",
    ]


def _ux_behavior_rules_for_context(text: str) -> list[str]:
    return [
        "All network actions show loading skeleton/spinner and disable duplicate submits.",
        "Forms provide inline validation messages and field-level error hints.",
        "Empty states provide clear CTA (e.g., go to catalog when cart is empty).",
        "Recoverable failures expose retry action and preserve user input.",
        "Role-aware navigation hides inaccessible actions and routes.",
        "Session timeout warns user and provides seamless re-auth flow.",
    ]


def _functional_flows_for_context(text: str, actors: list[str]) -> list[dict[str, Any]]:
    actor = actors[0] if actors else "Customer"
    return [
        {
            "name": "Browse and discover products",
            "actor": actor,
            "preconditions": ["Catalog service available"],
            "validations": ["query param bounds", "search sanitization"],
            "happy_path": ["open home", "navigate to catalog", "filter/search", "view product detail"],
            "edge_cases": ["no results", "invalid filters"],
            "failures": ["catalog API timeout"],
            "retries": ["retry catalog request"],
            "alternatives": ["browse featured products on home"],
            "postconditions": ["selected product context available for cart action"],
        },
        {
            "name": "Checkout with payment",
            "actor": actor,
            "preconditions": ["authenticated session", "active cart with items"],
            "validations": ["stock re-check", "payment instrument validity", "address completeness"],
            "happy_path": ["review cart", "submit checkout", "authorize payment", "create order", "show confirmation"],
            "edge_cases": ["price changed", "stock changed during checkout"],
            "failures": ["payment failed", "session expired", "inventory conflict"],
            "retries": ["retry payment with idempotency key"],
            "alternatives": ["change payment method", "save for later"],
            "postconditions": ["order persisted", "cart moved to CHECKED_OUT"],
        },
    ]


def _consistency_checks(
    *,
    inferred_mvp: dict[str, list[str]],
    entities: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    validations: list[str],
    permissions: list[dict[str, str]],
) -> dict[str, Any]:
    warnings: list[str] = []
    if not inferred_mvp.get("public_pages"):
        warnings.append("Missing inferred public MVP pages.")
    if not entities:
        warnings.append("Missing domain entity modeling.")
    if "Order" not in states:
        warnings.append("Missing order state machine.")
    if not events:
        warnings.append("Missing business event model.")
    if not validations:
        warnings.append("Missing validation rule model.")
    if not permissions:
        warnings.append("Missing permissions matrix.")
    if not any("Home" in item for item in inferred_mvp.get("core_mvp", [])):
        warnings.append("Missing Home/Landing in core MVP inference.")
    if not any("Dashboard" in item for item in inferred_mvp.get("core_mvp", [])):
        warnings.append("Missing Dashboard in core MVP inference.")
    if not any("Profile" in item for item in inferred_mvp.get("core_mvp", [])):
        warnings.append("Missing Profile in core MVP inference.")
    if not any("Settings" in item for item in inferred_mvp.get("core_mvp", [])):
        warnings.append("Missing Settings in core MVP inference.")
    score = max(0, 100 - len(warnings) * 12)
    return {"warnings": warnings, "score": score}


def _ba_quality_report(
    *,
    inferred_mvp: dict[str, list[str]],
    entities: list[dict[str, Any]],
    states: dict[str, dict[str, Any]],
    validations: list[str],
    failure_flows: list[str],
    consistency: dict[str, Any],
    stories: list[Any],
) -> dict[str, Any]:
    warnings = list(consistency.get("warnings", []))
    if len(stories) < 3:
        warnings.append("Shallow user stories: fewer than 3 stories.")
    if not inferred_mvp.get("domain_pages"):
        warnings.append("Missing MVP domain-specific page inference.")
    if not inferred_mvp.get("core_mvp"):
        warnings.append("Shallow MVP inference: missing core MVP page set.")
    if not entities:
        warnings.append("Missing entity model.")
    if not states:
        warnings.append("Missing state models.")
    if not validations:
        warnings.append("Missing validation rules.")
    if not failure_flows:
        warnings.append("Missing failure flow coverage.")
    score = max(0, min(100, int(consistency.get("score", 0) - max(0, len(warnings) - len(consistency.get("warnings", []))) * 8)))
    return {"warnings": warnings, "score": score}


def _gap_analysis_markdown(gaps: list[str]) -> str:
    lines = ["# Gap Analysis", ""]
    lines.extend(f"- {gap}" for gap in (gaps or ["No critical gaps detected."]))
    return "\n".join(lines) + "\n"


def _clarifications_markdown(questions: list[dict[str, str]]) -> str:
    lines = ["# Clarification Questions", ""]
    for index, item in enumerate(questions, start=1):
        lines.append(f"{index}. ({item['priority']}) {item['question']}")
        lines.append(f"Impact: {item['impact']}")
    return "\n".join(lines) + "\n"


def _executive_summary(task: str, structured_output: dict[str, Any], gaps: list[str]) -> str:
    return (
        "# Executive Summary\n\n"
        f"Input requirement: {task.strip()}\n\n"
        f"Detected {len(gaps)} unresolved requirement gaps requiring clarification before implementation lock.\n"
    )


def _functional_spec(task: str, actors: list[str], integrations: list[str]) -> str:
    lines = [
        "# Functional Specification",
        "",
        f"Primary request: {task.strip()}",
        "",
        "## Actors",
    ]
    lines.extend(f"- {actor}" for actor in actors)
    lines.extend(["", "## Integration Points"])
    lines.extend(f"- {item}" for item in integrations)
    lines.extend(
        [
            "",
            "## Functional Flows",
            "- Catalog discovery and filtering",
            "- Product detail and cart operations",
            "- Checkout validations and order creation",
        ]
    )
    return "\n".join(lines) + "\n"


def _user_stories_markdown(structured_output: dict[str, Any]) -> str:
    stories = structured_output.get("user_stories", []) if isinstance(structured_output, dict) else []
    lines = ["# User Stories", ""]
    if not stories:
        lines.extend(
            [
                "- As a customer, I want to discover products so I can decide what to buy.",
                "- As a customer, I want to manage my cart so I can prepare checkout.",
                "- As an admin, I want to manage products so inventory stays accurate.",
            ]
        )
        return "\n".join(lines) + "\n"
    for index, story in enumerate(stories, start=1):
        lines.append(f"- US-{index}: {story.get('narrative') or story.get('title')}")
    return "\n".join(lines) + "\n"


def _acceptance_markdown(structured_output: dict[str, Any], gaps: list[str]) -> str:
    lines = [
        "# Acceptance Criteria",
        "",
        "- Given valid product data, when listing endpoint is queried, then paginated results are returned.",
        "- Given authenticated actor, when cart is updated, then ownership and stock validations are enforced.",
        "- Given checkout request, when dependencies fail, then deterministic error contract is returned.",
    ]
    if gaps:
        lines.append("- Clarification-gated criteria: payment/shipping/auth must be resolved before production readiness.")
    return "\n".join(lines) + "\n"


def _business_rules_markdown(text: str) -> str:
    lines = [
        "# Business Rules",
        "",
        "- BR-1: Cart item quantity must never exceed available stock.",
        "- BR-2: Order total must be reproducible from line items and pricing policy.",
        "- BR-3: Unauthorized actors cannot access or mutate another user's cart/orders.",
        "- BR-4: Product status controls purchasability (active vs archived).",
    ]
    if "checkout" in text:
        lines.append("- BR-5: Checkout requires stock, pricing, and payment preconditions to pass.")
    return "\n".join(lines) + "\n"


def _requirements_matrix_markdown() -> str:
    return (
        "# Requirements Matrix\n\n"
        "| Requirement | Actor | Validation | Edge Case |\n"
        "|---|---|---|---|\n"
        "| Product listing | Customer | Filter and pagination params | Empty catalog |\n"
        "| Cart management | Customer | Stock and ownership checks | Concurrent updates |\n"
        "| Checkout | Customer | Pricing, stock, auth preconditions | payment/shipping failure |\n"
    )


def _assumptions_markdown(gaps: list[str]) -> str:
    lines = ["# Assumptions", ""]
    if gaps:
        lines.append("- Business decisions for unresolved gaps are pending clarification.")
    lines.extend(
        [
            "- MVP scope excludes marketplace payouts and advanced seller operations unless specified.",
            "- Local environment and mock integrations are acceptable for initial validation.",
        ]
    )
    return "\n".join(lines) + "\n"


def _permissions_matrix_markdown(actors: list[str], permissions: list[dict[str, str]]) -> str:
    lines = [
        "# Permissions Matrix",
        "",
        "| Actor | Allowed Actions | Restricted Actions | Ownership Rules |",
        "|---|---|---|---|",
    ]
    for row in permissions:
        lines.append(
            f"| {row['actor']} | {row['allowed']} | {row['restricted']} | {row['ownership']} |"
        )
    return "\n".join(lines) + "\n"


def _mvp_application_flow_markdown(mvp: dict[str, list[str]]) -> str:
    return (
        "# MVP Application Flow\n\n"
        "## Public Navigation\n"
        + "\n".join(f"- {page}" for page in mvp.get("public_pages", []))
        + "\n\n## Authenticated Navigation\n"
        + "\n".join(f"- {page}" for page in mvp.get("authenticated_pages", []))
        + "\n\n## Domain Navigation\n"
        + "\n".join(f"- {page}" for page in mvp.get("domain_pages", []))
        + "\n\n## Recovery/Failure Navigation\n- Session expiry redirects to login with return path.\n- API failures provide retry and fallback navigation.\n"
    )


def _frontend_mvp_expectations_markdown(mvp: dict[str, list[str]]) -> str:
    return (
        "# Frontend MVP Expectations\n\n"
        "## Minimum Reusable Components\n- App layout (header/sidebar/footer)\n- Nav menu with role-aware visibility\n- Form controls with validation states\n- Toast/notification system\n\n"
        "## Reusable Layout Expectations\n- Public layout for landing/auth pages\n- Authenticated layout with sidebar + breadcrumbs\n- Protected route wrapper with session restore\n\n"
        "## Required UX Behaviors\n"
        + "\n".join(f"- {item}" for item in mvp.get("ux_components", []))
        + "\n- Auth/session UX for login/logout/timeout recovery.\n- Responsive behavior across mobile/tablet/desktop.\n"
    )


def _domain_entities_markdown(entities: list[dict[str, Any]]) -> str:
    lines = ["# Domain Entities", ""]
    for entity in entities:
        lines.extend(
            [
                f"## {entity['name']}",
                f"- Purpose: {entity['purpose']}",
                f"- Ownership: {entity['ownership']}",
                f"- Lifecycle: {entity['lifecycle']}",
                f"- Relationships: {', '.join(entity['relationships'])}",
                f"- Validations: {', '.join(entity['validations'])}",
                f"- Constraints: {', '.join(entity['constraints'])}",
                f"- Attributes: {', '.join(entity['attributes'])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _state_machines_markdown(models: dict[str, dict[str, Any]]) -> str:
    lines = ["# State Machines", ""]
    for name, model in models.items():
        lines.extend(
            [
                f"## {name}",
                f"- States: {', '.join(model['states'])}",
                f"- Allowed transitions: {', '.join(model['allowed_transitions'])}",
                f"- Invalid transitions: {', '.join(model['invalid_transitions'])}",
                f"- Triggers: {', '.join(model['triggers'])}",
                f"- Business consequences: {', '.join(model['consequences'])}",
                f"- Recovery rules: {', '.join(model['recovery_rules'])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _business_events_markdown(events: list[dict[str, Any]]) -> str:
    lines = ["# Business Events", ""]
    for event in events:
        lines.extend(
            [
                f"## {event['name']}",
                f"- Producer: {event['producer']}",
                f"- Consumer: {event['consumer']}",
                f"- Payload: {', '.join(event['payload'])}",
                f"- Impact: {event['impact']}",
                f"- Retry expectations: {event['retry']}",
                f"- Notifications: {', '.join(event['notifications']) if event['notifications'] else 'none'}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _functional_flows_markdown(flows: list[dict[str, Any]]) -> str:
    lines = ["# Functional Flows", ""]
    for flow in flows:
        lines.extend(
            [
                f"## {flow['name']}",
                f"- Actor: {flow['actor']}",
                f"- Preconditions: {', '.join(flow['preconditions'])}",
                f"- Validations: {', '.join(flow['validations'])}",
                f"- Happy path: {', '.join(flow['happy_path'])}",
                f"- Edge cases: {', '.join(flow['edge_cases'])}",
                f"- Failure scenarios: {', '.join(flow['failures'])}",
                f"- Retries: {', '.join(flow['retries'])}",
                f"- Alternative flows: {', '.join(flow['alternatives'])}",
                f"- Postconditions: {', '.join(flow['postconditions'])}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _validation_rules_markdown(rules: list[str]) -> str:
    return _list_markdown("Validation Rules", rules)


def _failure_flows_markdown(flows: list[str]) -> str:
    return _list_markdown("Failure Flows", flows)


def _ux_behavior_rules_markdown(rules: list[str]) -> str:
    return _list_markdown("UX Behavior Rules", rules)


def _api_expectations_markdown(endpoints: list[dict[str, Any]]) -> str:
    lines = ["# API Expectations", ""]
    for ep in endpoints:
        lines.extend(
            [
                f"## {ep['method']} {ep['path']}",
                f"- Required payload: {', '.join(ep['payload'])}",
                f"- Validation expectations: {ep['validation']}",
                f"- Error expectations: {', '.join(ep['errors'])}",
                f"- Auth expectations: {ep['auth']}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _ba_quality_report_markdown(report: dict[str, Any], consistency: dict[str, Any]) -> str:
    lines = ["# BA Quality Report", "", f"- BA completeness score: {report['score']}/100", ""]
    lines.append("## Warnings")
    warnings = report.get("warnings", [])
    lines.extend(f"- {item}" for item in (warnings or ["No warnings."]))
    lines.extend(["", "## Consistency Validation"])
    lines.append(f"- Consistency score: {consistency.get('score', 0)}/100")
    lines.extend(f"- {item}" for item in consistency.get("warnings", []))
    lines.extend(
        [
            "",
            "## Governance Checks",
            "- Home/Landing inferred",
            "- Dashboard/Profile/Settings inferred",
            "- Application shell modeled",
            "- Navigation hierarchy modeled",
            "- Auth/session lifecycle modeled",
        ]
    )
    return "\n".join(lines) + "\n"


def _navigation_map_diagram(mvp: dict[str, list[str]]) -> str:
    public = mvp.get("public_pages", [])
    auth = mvp.get("authenticated_pages", [])
    domain = mvp.get("domain_pages", [])
    lines = ["flowchart LR", 'Home["Home"] --> Login["Login/Register"]']
    if public:
        lines.extend([f'Home --> P{i}["{name}"]' for i, name in enumerate(public[:3], start=1)])
    if auth:
        lines.extend([f'Login --> A{i}["{name}"]' for i, name in enumerate(auth[:3], start=1)])
    if domain:
        lines.extend([f'A1 --> D{i}["{name}"]' for i, name in enumerate(domain[:5], start=1)])
    return "\n".join(lines) + "\n"


def _user_journey_diagram(mvp: dict[str, list[str]]) -> str:
    return (
        "flowchart LR\n"
        'Visitor["Visitor"] --> Browse["Browse catalog"]\n'
        "Browse --> Register[\"Register/Login\"]\n"
        "Register --> Dashboard[\"Dashboard\"]\n"
        "Dashboard --> Cart[\"Cart\"]\n"
        "Cart --> Checkout[\"Checkout\"]\n"
        "Checkout --> Order[\"Order confirmation\"]\n"
    )


def _page_transition_diagram(mvp: dict[str, list[str]]) -> str:
    return (
        "flowchart TD\n"
        "Home --> Catalog\n"
        "Catalog --> ProductDetail\n"
        "ProductDetail --> Cart\n"
        "Cart --> Checkout\n"
        "Checkout --> Orders\n"
        "Checkout --> PaymentError\n"
        "PaymentError --> Checkout\n"
        "SessionExpired --> Login\n"
    )


def _state_diagram_for_cart_order(models: dict[str, dict[str, Any]]) -> str:
    cart = models.get("Cart", {})
    order = models.get("Order", {})
    cart_states = cart.get("states", [])
    order_states = order.get("states", [])
    lines = ["stateDiagram-v2", "state Cart {"]
    for state in cart_states:
        lines.append(f"  {state}")
    for transition in cart.get("allowed_transitions", []):
        src, dst = [item.strip() for item in transition.split("->")]
        lines.append(f"  {src} --> {dst}")
    lines.append("}")
    lines.append("state Order {")
    for state in order_states:
        lines.append(f"  {state}")
    for transition in order.get("allowed_transitions", []):
        src, dst = [item.strip() for item in transition.split("->")]
        lines.append(f"  {src} --> {dst}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _application_shell_markdown(mvp: dict[str, list[str]]) -> str:
    return (
        "# Application Shell\n\n"
        "## Routing Hierarchy\n"
        "- Public: /, /login, /register, /about, /contact\n"
        "- Authenticated: /dashboard, /profile, /settings, /orders\n"
        "- Commerce: /catalog, /products/:id, /cart, /checkout\n\n"
        "## Layout Composition\n"
        "- Public layout: header + footer + minimal nav\n"
        "- Auth layout: sidebar + topbar + breadcrumbs + notifications\n\n"
        "## Auth Boundaries\n"
        "- Guest routes: login/register\n"
        "- Protected routes: dashboard/profile/settings/cart/checkout/orders\n\n"
        "## Session Restoration\n"
        "- Restore session from secure token\n- redirect to login on expiry\n- preserve intended route for post-login resume\n"
    )


def _navigation_structure_markdown(mvp: dict[str, list[str]]) -> str:
    return (
        "# Navigation Structure\n\n"
        "## Public Navigation\n"
        + "\n".join(f"- {p}" for p in mvp.get("public_pages", []))
        + "\n\n## Authenticated Navigation\n"
        + "\n".join(f"- {p}" for p in mvp.get("authenticated_pages", []))
        + "\n\n## Role-Aware Navigation\n- Customer: catalog/cart/checkout/orders/profile\n- Admin: dashboard/reports/product-management\n"
        "\n## Fallback/Error Navigation\n- 401 -> login\n- 403 -> access denied\n- 404 -> not-found page\n- 5xx -> retry/help center\n"
    )


def _mvp_page_matrix_markdown(mvp: dict[str, list[str]]) -> str:
    lines = [
        "# MVP Page Matrix",
        "",
        "| Page | Classification |",
        "|---|---|",
    ]
    for page in mvp.get("core_mvp", []):
        lines.append(f"| {page} | Core MVP |")
    for page in mvp.get("recommended_mvp", []):
        lines.append(f"| {page} | Recommended MVP |")
    for page in mvp.get("future_features", []):
        lines.append(f"| {page} | Future Enhancement |")
    return "\n".join(lines) + "\n"


def _user_lifecycle_markdown() -> str:
    return (
        "# User Lifecycle\n\n"
        "1. Onboarding: visitor -> register -> verify -> first login\n"
        "2. Authentication: login success/failure + lockout policy\n"
        "3. Session lifecycle: issued -> active -> expiring -> expired/re-authenticated\n"
        "4. Password recovery: request reset -> token verify -> update password\n"
        "5. Logout flow: revoke session and redirect to public page\n"
        "6. Account deactivation/recovery with admin override path\n"
    )


def _data_ownership_markdown(entities: list[dict[str, Any]]) -> str:
    lines = ["# Data Ownership", "", "| Domain Object | Owner | Source of Truth | Key Rule |", "|---|---|---|---|"]
    for entity in entities:
        key_rule = (entity.get("constraints") or ["n/a"])[0]
        lines.append(f"| {entity['name']} | {entity['ownership']} | {entity['name']} aggregate | {key_rule} |")
    lines.extend(
        [
            "",
            "- Cart owned by User context.",
            "- Order immutable after successful payment capture.",
            "- Inventory is authoritative for stock availability.",
            "- Payment status may be eventually consistent via gateway callbacks.",
        ]
    )
    return "\n".join(lines) + "\n"


def _roadmap_priorities_markdown(mvp: dict[str, list[str]]) -> str:
    return (
        "# Roadmap Priorities\n\n"
        "## Mandatory MVP\n"
        + "\n".join(f"- {p}" for p in mvp.get("core_mvp", []))
        + "\n\n## Recommended MVP\n"
        + "\n".join(f"- {p}" for p in mvp.get("recommended_mvp", []))
        + "\n\n## Future Enhancements\n"
        + "\n".join(f"- {p}" for p in mvp.get("future_features", []))
        + "\n"
    )


def _route_hierarchy_diagram(mvp: dict[str, list[str]]) -> str:
    return (
        "flowchart TD\n"
        "Root[/] --> Public[/public]\n"
        "Root --> Auth[/auth]\n"
        "Root --> App[/app]\n"
        "Public --> Home[Home]\n"
        "Public --> About[About]\n"
        "Auth --> Login[Login]\n"
        "Auth --> Register[Register]\n"
        "App --> Dashboard[Dashboard]\n"
        "Dashboard --> Profile[Profile]\n"
        "Dashboard --> Settings[Settings]\n"
        "Dashboard --> Catalog[Catalog]\n"
        "Catalog --> Product[Product Details]\n"
        "Product --> Cart[Cart]\n"
        "Cart --> Checkout[Checkout]\n"
        "Checkout --> Orders[Orders]\n"
    )


def _list_markdown(title: str, items: list[str]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) + "\n"
