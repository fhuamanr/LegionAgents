"""Repository-aware context providers."""

from pathlib import Path
import re

from core.contracts.context import ContextPriority
from core.context_engineering.models import ContextEngineeringRequest, ContextItem, ContextItemSource
from core.context_engineering.summarization import RepositorySummarizer


class RepositorySummaryProvider:
    """Provides repository summaries and semantically selected files as context items."""

    _ignored_directories = {
        ".git",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        ".next",
        ".venv",
        "venv",
        "dist",
        "build",
        "outputs",
    }
    _text_suffixes = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".md",
        ".mmd",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".css",
        ".html",
    }
    _architecture_path_hints = (
        "core/contracts/",
        "core/runtime/",
        "core/graph/",
        "core/context_engineering/",
        "core/governance/",
        "repository/standards/",
        "agents/",
        "diagram",
        "docker-compose",
    )

    def __init__(self, summarizer: RepositorySummarizer | None = None) -> None:
        self._summarizer = summarizer or RepositorySummarizer()

    async def provide(
        self,
        repository_path: Path | None,
        request: ContextEngineeringRequest | None = None,
    ) -> tuple[ContextItem, ...]:
        if repository_path is None:
            return tuple()
        if not repository_path.exists():
            return tuple()

        items: list[ContextItem] = []
        summary = await self._summarizer.summarize(repository_path)
        if summary.strip():
            items.append(ContextItem(
                id="repository-summary",
                source=ContextItemSource.REPOSITORY_SUMMARY,
                title="Repository Summary",
                content=summary,
                priority=ContextPriority.HIGH,
                token_hint=max(1, len(summary) // 4),
                metadata={"path": str(repository_path)},
            ))
        if request is not None and request.config.selected_repository_file_limit > 0:
            items.extend(self._selected_file_items(repository_path, request))
        return tuple(items)

    def _selected_file_items(
        self,
        repository_path: Path,
        request: ContextEngineeringRequest,
    ) -> tuple[ContextItem, ...]:
        candidates: list[tuple[int, Path, str, bool]] = []
        for path in sorted(repository_path.rglob("*")):
            if not self._should_read(path, repository_path, request):
                continue
            relative = path.relative_to(repository_path).as_posix()
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if not content.strip():
                continue
            architecture_context = self._is_architecture_file(relative)
            score = self._score_file(relative, content, request, architecture_context)
            if score <= 0 and not architecture_context:
                continue
            candidates.append((score, path, content, architecture_context))

        selected = sorted(
            candidates,
            key=lambda item: (-int(item[3]), -item[0], item[1].as_posix()),
        )[: request.config.repository_file_limit]
        selected = selected[: request.config.selected_repository_file_limit]
        return tuple(
            self._file_item(repository_path, path, content, score, architecture_context, request)
            for score, path, content, architecture_context in selected
        )

    def _should_read(
        self,
        path: Path,
        repository_path: Path,
        request: ContextEngineeringRequest,
    ) -> bool:
        if not path.is_file() or path.suffix.lower() not in self._text_suffixes:
            return False
        relative_parts = path.relative_to(repository_path).parts
        if any(part in self._ignored_directories for part in relative_parts):
            return False
        try:
            if path.stat().st_size > request.config.repository_file_max_bytes:
                return False
        except OSError:
            return False
        return True

    def _file_item(
        self,
        repository_path: Path,
        path: Path,
        content: str,
        score: int,
        architecture_context: bool,
        request: ContextEngineeringRequest,
    ) -> ContextItem:
        relative = path.relative_to(repository_path).as_posix()
        body = self._snippet(content, request.config.repository_file_token_soft_limit)
        rendered = f"Path: {relative}\n\n{body}"
        return ContextItem(
            id=f"repository-file-{relative.replace('/', '-')}",
            source=ContextItemSource.REPOSITORY_FILE,
            title=f"Repository File: {relative}",
            content=rendered,
            priority=ContextPriority.HIGH if architecture_context else ContextPriority.NORMAL,
            token_hint=max(1, len(rendered) // 4),
            metadata={
                "path": relative,
                "repository_root": str(repository_path),
                "repository_relevance": score,
                "architecture_context": architecture_context,
            },
        )

    def _score_file(
        self,
        relative: str,
        content: str,
        request: ContextEngineeringRequest,
        architecture_context: bool,
    ) -> int:
        query = " ".join(
            part
            for part in (
                request.agent_name,
                request.task,
                request.architecture_context or "",
                " ".join(request.upstream_context),
            )
            if part
        )
        terms = self._terms(query)
        relative_text = relative.lower().replace("_", " ").replace("-", " ").replace("/", " ")
        haystack = f"{relative_text}\n{content}".lower()
        score = sum(3 if term in relative_text else 1 for term in terms if term in haystack)
        if architecture_context:
            score += 8
        if request.agent_name.lower() in relative.lower():
            score += 6
        if "context engineering" in query.lower() and "context engineering" in relative_text:
            score += 12
        if "token budgeting" in query.lower() and "budget" in relative_text:
            score += 8
        return score

    def _is_architecture_file(self, relative: str) -> bool:
        lowered = relative.lower()
        return any(hint in lowered for hint in self._architecture_path_hints)

    def _terms(self, text: str) -> set[str]:
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "from",
            "that",
            "this",
            "into",
            "must",
            "real",
            "runtime",
            "system",
            "agent",
            "agents",
        }
        return {
            term
            for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
            if term not in stop_words
        }

    def _snippet(self, content: str, token_limit: int) -> str:
        character_limit = token_limit * 4
        if len(content) <= character_limit:
            return content.strip()
        lines = [line.rstrip() for line in content.splitlines()]
        head: list[str] = []
        total = 0
        for line in lines:
            line_length = len(line) + 1
            if head and total + line_length > character_limit:
                break
            head.append(line)
            total += line_length
        return "\n".join(head).strip()

