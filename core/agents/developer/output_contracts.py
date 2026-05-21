"""Developer agent output contract definitions."""

from core.contracts.artifacts import ArtifactKind
from core.contracts.outputs import (
    ContractFieldRequirement,
    OutputContract,
    OutputContractKind,
)


def build_developer_output_contract(agent_name: str = "developer") -> OutputContract:
    """Create the developer agent output contract."""

    return OutputContract(
        kind=OutputContractKind.DEVELOPMENT_PLAN,
        agent_name=agent_name,
        name="Developer Implementation Contract",
        description=(
            "Structured implementation output owned only by the developer agent. "
            "The developer may plan and describe code changes, tests, validations, "
            "and produced source artifacts, but must not redefine BA, architecture, QA, docs, or PR ownership."
        ),
        required_fields=(
            ContractFieldRequirement(
                name="summary",
                description="Concise summary of the implementation intent or completed implementation.",
            ),
            ContractFieldRequirement(
                name="work_items",
                description="Implementation work items with target paths and test expectations.",
                value_type="array[DevelopmentWorkItem]",
            ),
            ContractFieldRequirement(
                name="artifacts",
                description="Source code or test artifacts produced by the developer agent.",
                value_type="array[Artifact]",
            ),
            ContractFieldRequirement(
                name="code_changes",
                description="Code generation or modification proposals.",
                required=False,
                value_type="array[CodeChangeProposal]",
            ),
            ContractFieldRequirement(
                name="tests",
                description="Test generation proposals and validation commands.",
                required=False,
                value_type="array[TestGenerationProposal]",
            ),
            ContractFieldRequirement(
                name="refactoring_suggestions",
                description="Refactoring suggestions with rationale and risk.",
                required=False,
                value_type="array[RefactoringSuggestion]",
            ),
            ContractFieldRequirement(
                name="commit_message",
                description="Suggested commit message for developer-owned changes.",
                required=False,
            ),
            ContractFieldRequirement(
                name="pr_draft",
                description="Draft PR title, description, and checklist text only.",
                required=False,
                value_type="PullRequestDraft",
            ),
            ContractFieldRequirement(
                name="risks",
                description="Implementation risks discovered by the developer agent.",
                required=False,
                value_type="array[RiskItem]",
            ),
            ContractFieldRequirement(
                name="dependencies",
                description="Technical dependencies that block or shape implementation.",
                required=False,
                value_type="array[DependencyItem]",
            ),
        ),
        artifact_kinds=(ArtifactKind.SOURCE_CODE, ArtifactKind.GENERIC),
    )
