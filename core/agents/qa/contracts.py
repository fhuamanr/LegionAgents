"""QA runtime contracts."""

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from core.contracts.base import ContractBaseModel
from core.contracts.outputs import OutputContract, OutputSeverity


class QACapability(StrEnum):
    """QA runtime capabilities."""

    UNIT_TEST_GENERATION = "unit_test_generation"
    INTEGRATION_TEST_GENERATION = "integration_test_generation"
    PLAYWRIGHT_AUTOMATION = "playwright_automation"
    SELENIUM_AUTOMATION = "selenium_automation"
    SCREENSHOT_GENERATION = "screenshot_generation"
    BUG_REPORTING = "bug_reporting"
    SEVERITY_CLASSIFICATION = "severity_classification"
    EVIDENCE_GENERATION = "evidence_generation"


class QARuntimeConfig(ContractBaseModel):
    """Configuration for the autonomous QA runtime."""

    agent_name: str = "qa"
    context_path: Path
    repository_path: Path = Field(default_factory=Path.cwd)
    evidence_output_path: Path = Path("outputs/qa")
    output_contract: OutputContract
    max_context_token_hint: int | None = Field(default=None, ge=1)
    required_rule_files: tuple[str, ...] = (
        "gravity.md",
        "anti-gravity.md",
        "severity-rules.md",
        "test-strategy.md",
    )
    capabilities: tuple[QACapability, ...] = (
        QACapability.UNIT_TEST_GENERATION,
        QACapability.INTEGRATION_TEST_GENERATION,
        QACapability.PLAYWRIGHT_AUTOMATION,
        QACapability.SELENIUM_AUTOMATION,
        QACapability.SCREENSHOT_GENERATION,
        QACapability.BUG_REPORTING,
        QACapability.SEVERITY_CLASSIFICATION,
        QACapability.EVIDENCE_GENERATION,
    )
    additional_instructions: tuple[str, ...] = Field(default_factory=tuple)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserAction(StrEnum):
    """Browser automation action kinds."""

    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SCREENSHOT = "screenshot"
    ASSERT_VISIBLE = "assert_visible"


class BrowserAutomationStep(ContractBaseModel):
    """Browser automation instruction emitted or executed by QA."""

    action: BrowserAction
    target: str | None = None
    value: str | None = None
    description: str = Field(min_length=1)


class BrowserAutomationResult(ContractBaseModel):
    """Browser automation result."""

    step: BrowserAutomationStep
    success: bool
    screenshot_path: str | None = None
    message: str | None = None


class SeverityClassification(ContractBaseModel):
    """Severity classification result."""

    severity: OutputSeverity
    rationale: str = Field(min_length=1)
