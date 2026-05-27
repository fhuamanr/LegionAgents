# Task

Workflow type: general_delivery

User instruction: quiero hacer 1 e-commerce tipo mercadolibre, que tenga vista de los productos, usuarios , carrito de compras, sin integraciones, un MVP completo.

# Output Schema

QAOutput

# QA Output Requirements

Required minimal JSON shape:
{
  "agent_name": "qa",
  "summary": "Short QA evaluation summary.",
  "test_results": [],
  "issues_found": [],
  "recommendations": [],
  "status": "passed"
}
If no tests are available, still provide agent_name and summary.

# Upstream Artifacts

- requirements: ba structured output from ba
- generic: governance_report.json from ba
- architecture: architect structured output from architect
- generic: governance_report.json from architect
- source_code: developer structured output from developer
- test_report: qa structured output from qa