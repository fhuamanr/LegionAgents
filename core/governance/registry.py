"""Enterprise standards registry."""

from pathlib import Path

from core.governance.loader import MarkdownPolicyLoader
from core.governance.models import GovernancePolicy, RuleSource


class EnterpriseStandardsRegistry:
    """Loads enterprise standards into governance policies."""

    def __init__(
        self,
        standards_root: Path,
        loader: MarkdownPolicyLoader | None = None,
    ) -> None:
        self._standards_root = standards_root
        self._loader = loader or MarkdownPolicyLoader()

    async def load(self) -> GovernancePolicy:
        return await self._loader.load(
            root_path=self._standards_root,
            scope="enterprise",
            source=RuleSource.ENTERPRISE_STANDARD,
        )

