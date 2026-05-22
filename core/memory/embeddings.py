"""Embedding provider abstractions for semantic memory."""

from abc import ABC, abstractmethod
from hashlib import blake2b
from math import sqrt


class EmbeddingProvider(ABC):
    """Async embedding provider boundary."""

    @abstractmethod
    async def embed(self, text: str) -> tuple[float, ...]:
        """Create an embedding for text."""


class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding provider for development and tests."""

    def __init__(self, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than zero")
        self._dimensions = dimensions

    async def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0 for _ in range(self._dimensions)]
        for token in self._tokens(text):
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            vector[index] += 1.0
        norm = sqrt(sum(value * value for value in vector))
        if norm == 0:
            return tuple(vector)
        return tuple(value / norm for value in vector)

    def _tokens(self, text: str) -> tuple[str, ...]:
        normalized = "".join(character.lower() if character.isalnum() else " " for character in text)
        return tuple(token for token in normalized.split() if token)
