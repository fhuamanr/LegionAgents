"""Repository provider extension boundaries."""

from abc import ABC, abstractmethod

from core.contracts.repository import PullRequestPreparation


class RepositoryProviderAdapter(ABC):
    """Provider-specific repository hosting integration boundary."""

    @abstractmethod
    async def prepare_remote_pull_request(self, preparation: PullRequestPreparation) -> PullRequestPreparation:
        """Prepare provider-specific pull request metadata."""


class GitHubRepositoryProvider(RepositoryProviderAdapter):
    """Future GitHub integration boundary."""

    async def prepare_remote_pull_request(self, preparation: PullRequestPreparation) -> PullRequestPreparation:
        raise NotImplementedError("GitHub pull request integration is not implemented yet.")


class GitLabRepositoryProvider(RepositoryProviderAdapter):
    """Future GitLab SaaS integration boundary."""

    async def prepare_remote_pull_request(self, preparation: PullRequestPreparation) -> PullRequestPreparation:
        raise NotImplementedError("GitLab pull request integration is not implemented yet.")
