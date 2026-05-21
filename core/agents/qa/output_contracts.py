"""QA output contract definitions."""

from core.contracts.artifacts import ArtifactKind
from core.contracts.outputs import ContractFieldRequirement, OutputContract, OutputContractKind


def build_qa_output_contract(agent_name: str = "qa") -> OutputContract:
    """Create the QA agent output contract."""

    return OutputContract(
        kind=OutputContractKind.QUALITY_REPORT,
        agent_name=agent_name,
        name="QA Validation Contract",
        description=(
            "Structured QA output covering test reports, screenshots, execution logs, "
            "bug summaries, severity classification, evidence, and coverage summaries."
        ),
        required_fields=(
            ContractFieldRequirement(
                name="summary",
                description="Concise QA validation summary.",
            ),
            ContractFieldRequirement(
                name="passed",
                description="Whether QA validation passed.",
                value_type="boolean",
            ),
            ContractFieldRequirement(
                name="findings",
                description="QA findings with severity and evidence.",
                value_type="array[QualityFinding]",
            ),
            ContractFieldRequirement(
                name="test_reports",
                description="Unit, integration, browser, and automation test reports.",
                value_type="array[TestReport]",
            ),
            ContractFieldRequirement(
                name="screenshots",
                description="Screenshot evidence produced by QA automation.",
                required=False,
                value_type="array[ScreenshotEvidence]",
            ),
            ContractFieldRequirement(
                name="execution_logs",
                description="Execution logs generated during QA validation.",
                required=False,
                value_type="array[ExecutionLog]",
            ),
            ContractFieldRequirement(
                name="bug_summaries",
                description="Bug summaries with severity and reproduction steps.",
                required=False,
                value_type="array[BugSummary]",
            ),
            ContractFieldRequirement(
                name="coverage",
                description="Coverage summary when available.",
                required=False,
                value_type="CoverageSummary",
            ),
        ),
        artifact_kinds=(ArtifactKind.TEST_REPORT, ArtifactKind.GENERIC),
    )

