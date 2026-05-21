"""Context engineering system for multi-agent execution."""

from core.context_engineering.budgeting import TokenBudgetManager
from core.context_engineering.compression import ContextCompressor, ExtractiveContextCompressor
from core.context_engineering.engine import ContextEngineeringEngine
from core.context_engineering.memory import MemoryContextProvider
from core.context_engineering.models import (
    ContextEngineeringConfig,
    ContextEngineeringRequest,
    ContextEngineeringResult,
    ContextItem,
    ContextItemSource,
)
from core.context_engineering.repository import RepositorySummaryProvider
from core.context_engineering.selection import ContextSelector, SmartContextSelector
from core.context_engineering.summarization import ArchitectureSummarizer, RepositorySummarizer

__all__ = [
    "ArchitectureSummarizer",
    "ContextCompressor",
    "ContextEngineeringConfig",
    "ContextEngineeringEngine",
    "ContextEngineeringRequest",
    "ContextEngineeringResult",
    "ContextItem",
    "ContextItemSource",
    "ContextSelector",
    "ExtractiveContextCompressor",
    "MemoryContextProvider",
    "RepositorySummarizer",
    "RepositorySummaryProvider",
    "SmartContextSelector",
    "TokenBudgetManager",
]

