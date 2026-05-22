"""Language-aware dependency analysis for repository modules."""

import ast
import re
from pathlib import Path

from core.contracts.repository_intelligence import (
    DependencyRelationshipKind,
    ModuleDependency,
    ModuleNode,
    RepositoryFileIndex,
)


class DependencyAnalyzer:
    """Builds module nodes and dependency edges from scanned repository files."""

    _ts_import_pattern = re.compile(
        r"(?:import\s+(?:[^'\"]+\s+from\s+)?|export\s+[^'\"]+\s+from\s+|require\()\s*['\"]([^'\"]+)['\"]"
    )

    async def analyze(
        self,
        root_path: Path,
        files: tuple[RepositoryFileIndex, ...],
    ) -> tuple[tuple[ModuleNode, ...], tuple[ModuleDependency, ...]]:
        """Analyze file-level module relationships."""

        nodes = tuple(self._node_for(file) for file in files)
        file_by_module = self._module_index(files)
        edges: list[ModuleDependency] = []
        for file in files:
            if file.language == "python":
                edges.extend(self._python_edges(root_path, file, file_by_module))
            elif file.language in {"typescript", "javascript"}:
                edges.extend(self._typescript_edges(root_path, file, file_by_module))
            elif file.is_config:
                edges.extend(self._config_edges(file))
        return nodes, tuple(edges)

    def _node_for(self, file: RepositoryFileIndex) -> ModuleNode:
        kind = "test" if file.is_test else "config" if file.is_config else "documentation" if file.is_documentation else "file"
        return ModuleNode(
            id=file.path,
            label=Path(file.path).name,
            path=file.path,
            language=file.language,
            kind=kind,
            metadata={"size_bytes": file.size_bytes},
        )

    def _module_index(self, files: tuple[RepositoryFileIndex, ...]) -> dict[str, str]:
        index: dict[str, str] = {}
        for file in files:
            path = Path(file.path)
            if file.language == "python":
                module = ".".join(path.with_suffix("").parts)
                if module.endswith(".__init__"):
                    module = module.removesuffix(".__init__")
                index[module] = file.path
            if file.language in {"typescript", "javascript"}:
                stem_path = path.with_suffix("").as_posix()
                index[stem_path] = file.path
                index[f"./{stem_path}"] = file.path
        return index

    def _python_edges(
        self,
        root_path: Path,
        file: RepositoryFileIndex,
        file_by_module: dict[str, str],
    ) -> list[ModuleDependency]:
        text = self._read_text(root_path / file.path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        edges: list[ModuleDependency] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    edges.append(self._edge_from_import(file.path, alias.name, file_by_module))
            elif isinstance(node, ast.ImportFrom) and node.module:
                edges.append(self._edge_from_import(file.path, node.module, file_by_module))
        return edges

    def _typescript_edges(
        self,
        root_path: Path,
        file: RepositoryFileIndex,
        file_by_module: dict[str, str],
    ) -> list[ModuleDependency]:
        text = self._read_text(root_path / file.path)
        base_dir = Path(file.path).parent.as_posix()
        edges: list[ModuleDependency] = []
        for match in self._ts_import_pattern.finditer(text):
            import_name = match.group(1)
            target = self._resolve_ts_import(base_dir, import_name, file_by_module)
            edges.append(
                ModuleDependency(
                    source=file.path,
                    target=target,
                    kind=DependencyRelationshipKind.IMPORTS,
                    import_name=import_name,
                    evidence=file.path,
                )
            )
        return edges

    def _config_edges(self, file: RepositoryFileIndex) -> list[ModuleDependency]:
        if file.path.endswith("package.json"):
            return [
                ModuleDependency(
                    source=file.path,
                    target="frontend",
                    kind=DependencyRelationshipKind.CONFIGURES,
                    evidence=file.path,
                )
            ]
        if file.path in {"requirements.txt", "pyproject.toml"}:
            return [
                ModuleDependency(
                    source=file.path,
                    target="python-runtime",
                    kind=DependencyRelationshipKind.CONFIGURES,
                    evidence=file.path,
                )
            ]
        return []

    def _edge_from_import(
        self,
        source: str,
        import_name: str,
        file_by_module: dict[str, str],
    ) -> ModuleDependency:
        target = self._resolve_python_import(import_name, file_by_module)
        kind = DependencyRelationshipKind.TESTS if self._is_test_source(source) else DependencyRelationshipKind.IMPORTS
        return ModuleDependency(source=source, target=target, kind=kind, import_name=import_name, evidence=source)

    def _resolve_python_import(self, import_name: str, file_by_module: dict[str, str]) -> str:
        parts = import_name.split(".")
        for index in range(len(parts), 0, -1):
            candidate = ".".join(parts[:index])
            if candidate in file_by_module:
                return file_by_module[candidate]
        return import_name

    def _resolve_ts_import(self, base_dir: str, import_name: str, file_by_module: dict[str, str]) -> str:
        if not import_name.startswith("."):
            return import_name
        joined = Path(base_dir, import_name).as_posix() if base_dir != "." else import_name
        normalized = str(Path(joined)).replace("\\", "/").removeprefix("./")
        for candidate in (normalized, f"{normalized}/index"):
            if candidate in file_by_module:
                return file_by_module[candidate]
        return normalized

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _is_test_source(self, path: str) -> bool:
        lowered = path.lower()
        return lowered.startswith("tests/") or "/tests/" in lowered or lowered.endswith(".test.tsx")
