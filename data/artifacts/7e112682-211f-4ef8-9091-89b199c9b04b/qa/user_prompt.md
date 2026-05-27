# Task

Deliver login feature

Uploaded context (Login story):
As a user, I can log in.

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
- architecture: architect structured output from architect
- source_code: developer structured output from developer