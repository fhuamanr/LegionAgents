"""Context loading package."""

from core.context.assemblers import ContextPackageAssembler
from core.context.classifiers import ContextSourceClassifier
from core.context.loaders import AgentContextLoader, FileSystemAgentContextLoader
from core.context.loaders import FileSystemContextSourceDiscoverer, ContextSourceDiscoverer
from core.context.readers import ContextDocumentReader, FileSystemContextDocumentReader
from core.context.registry import AgentRegistry, FileSystemAgentRegistry

__all__ = [
    "AgentContextLoader",
    "AgentRegistry",
    "ContextDocumentReader",
    "ContextPackageAssembler",
    "ContextSourceClassifier",
    "ContextSourceDiscoverer",
    "FileSystemAgentContextLoader",
    "FileSystemContextDocumentReader",
    "FileSystemContextSourceDiscoverer",
    "FileSystemAgentRegistry",
]
