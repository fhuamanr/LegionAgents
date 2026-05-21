"""Composed memory system."""

from core.memory.adr import ADRMemory
from core.memory.bugs import BugMemory
from core.memory.checkpoints import CheckpointMemory
from core.memory.history import ExecutionHistoryMemory
from core.memory.long_term import LongTermMemory
from core.memory.repository import InMemoryMemoryRepository, MemoryRepository
from core.memory.short_term import ShortTermMemory
from core.memory.vector import InMemoryVectorMemoryRepository, VectorMemory


class MemorySystem:
    """Composition root for platform memory services."""

    def __init__(self, repository: MemoryRepository | None = None) -> None:
        self.repository = repository or InMemoryMemoryRepository()
        self.short_term = ShortTermMemory(self.repository)
        self.long_term = LongTermMemory(self.repository)
        self.execution_history = ExecutionHistoryMemory(self.repository)
        self.adr = ADRMemory(self.repository)
        self.bugs = BugMemory(self.repository)
        self.checkpoints = CheckpointMemory(self.repository)
        self.vector = VectorMemory(InMemoryVectorMemoryRepository(self.repository))
