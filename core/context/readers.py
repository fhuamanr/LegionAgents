"""Context document readers."""

from abc import ABC, abstractmethod
from pathlib import Path


class ContextDocumentReader(ABC):
    """Reads source content for context loading."""

    @abstractmethod
    async def read_text(self, path: Path) -> str:
        """Read a context source as text."""


class FileSystemContextDocumentReader(ContextDocumentReader):
    """Filesystem-backed document reader."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self._encoding = encoding

    async def read_text(self, path: Path) -> str:
        return path.read_text(encoding=self._encoding)

