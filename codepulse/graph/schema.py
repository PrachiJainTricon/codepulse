"""Graph schema and mapping helpers for Neo4j ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileNode:
    repo: str
    path: str
    language: str
    hash: str
    lines_of_code: int = 0
    is_test: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileNode":
        max_line = max((s.get("end_line", 0) for s in data.get("symbols", [])), default=0)
        # Extract repo from path (format: "repo_name/file.py")
        full_path = str(data.get("path", ""))
        repo = full_path.split("/")[0] if "/" in full_path else ""
        rel_path = full_path.split("/", 1)[1] if "/" in full_path else full_path
        return cls(
            repo=repo,
            path=rel_path,
            language=str(data.get("language", "")),
            hash=str(data.get("hash", "")),
            lines_of_code=max_line,
            is_test="test" in rel_path.lower(),
        )


@dataclass(frozen=True)
class SymbolNode:
    repo: str
    name: str
    qualified_name: str
    type: str
    start_line: int
    end_line: int
    file_path: str
    is_test: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: str) -> "SymbolNode":
        name = str(data.get("name", ""))
        qualified_name = str(data.get("qualified_name", ""))
        # Extract repo from qualified_name (format: "repo_name.module.symbol")
        repo = qualified_name.split(".")[0] if qualified_name else ""
        return cls(
            repo=repo,
            name=name,
            qualified_name=qualified_name,
            type=str(data.get("type", "")),
            start_line=int(data.get("start_line", 0)),
            end_line=int(data.get("end_line", 0)),
            file_path=file_path,
            is_test=name.startswith("test_") or "test" in file_path.lower(),
        )


@dataclass(frozen=True)
class PackageNode:
    repo: str
    name: str
    is_external: bool = True
    is_builtin: bool = False


_PYTHON_STDLIB = {
    "abc",
    "argparse",
    "collections",
    "datetime",
    "functools",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "os",
    "pathlib",
    "re",
    "sqlite3",
    "subprocess",
    "sys",
    "typing",
    "unittest",
    "urllib",
    "uuid",
}


def parse_import_statement(import_str: str) -> str | None:
    text = import_str.strip()
    if text.startswith("import "):
        return text.replace("import ", "", 1).split(" as ", 1)[0].strip()
    if text.startswith("from ") and " import " in text:
        return text.replace("from ", "", 1).split(" import ", 1)[0].strip()
    return None


class GraphMapper:
    """Map parse-directory JSON output into graph nodes and relationships."""

    @staticmethod
    def extract_file_nodes(json_data: dict[str, Any]) -> list[FileNode]:
        return [FileNode.from_dict(result) for result in json_data.get("results", [])]

    @staticmethod
    def extract_symbol_nodes(json_data: dict[str, Any]) -> list[SymbolNode]:
        nodes: list[SymbolNode] = []
        for result in json_data.get("results", []):
            file_path = str(result.get("path", ""))
            for symbol in result.get("symbols", []):
                nodes.append(SymbolNode.from_dict(symbol, file_path))
        return nodes

    @staticmethod
    def extract_package_nodes(json_data: dict[str, Any]) -> list[PackageNode]:
        # Get repo name from JSON root
        repo_name = json_data.get("repo_name", "")
        packages: dict[str, PackageNode] = {}
        for result in json_data.get("results", []):
            for symbol in result.get("symbols", []):
                for import_str in symbol.get("imports", []):
                    module_name = parse_import_statement(str(import_str))
                    if not module_name or module_name in packages:
                        continue
                    root_module = module_name.split(".", 1)[0]
                    packages[module_name] = PackageNode(
                        repo=repo_name,
                        name=module_name,
                        is_external=not module_name.startswith("."),
                        is_builtin=root_module in _PYTHON_STDLIB,
                    )
        return list(packages.values())

    @staticmethod
    def extract_contains_relationships(json_data: dict[str, Any]) -> list[dict[str, str]]:
        rels: list[dict[str, str]] = []
        repo_name = json_data.get("repo_name", "")
        for result in json_data.get("results", []):
            file_path = str(result.get("path", ""))
            for symbol in result.get("symbols", []):
                rels.append({"repo": repo_name, "from": file_path, "to": str(symbol.get("qualified_name", ""))})
        return rels

    @staticmethod
    def extract_calls_relationships(json_data: dict[str, Any]) -> list[dict[str, Any]]:
        all_symbols = GraphMapper.extract_symbol_nodes(json_data)
        known = {symbol.qualified_name for symbol in all_symbols}
        by_name: dict[str, str] = {}
        for symbol in all_symbols:
            by_name.setdefault(symbol.name, symbol.qualified_name)

        rels: list[dict[str, Any]] = []
        for result in json_data.get("results", []):
            file_path = str(result.get("path", ""))
            same_file = {
                symbol.name: symbol.qualified_name
                for symbol in all_symbols
                if symbol.file_path == file_path
            }
            for symbol in result.get("symbols", []):
                caller = str(symbol.get("qualified_name", ""))
                for call_name in symbol.get("calls", []):
                    resolved = GraphMapper._resolve_call_target(
                        str(call_name), same_file=same_file, all_by_name=by_name
                    )
                    rels.append({
                        "from": caller,
                        "to": resolved,
                        "resolved": resolved in known,
                    })
        return rels

    @staticmethod
    def extract_imports_relationships(json_data: dict[str, Any]) -> list[dict[str, str]]:
        repo_name = json_data.get("repo_name", "")
        rels: list[dict[str, str]] = []
        for result in json_data.get("results", []):
            for symbol in result.get("symbols", []):
                caller = str(symbol.get("qualified_name", ""))
                for import_str in symbol.get("imports", []):
                    module_name = parse_import_statement(str(import_str))
                    if module_name:
                        rels.append({"repo": repo_name, "from": caller, "to": module_name})
        return rels

    @staticmethod
    def _resolve_call_target(
        call_name: str,
        *,
        same_file: dict[str, str],
        all_by_name: dict[str, str],
    ) -> str:
        text = call_name.strip()
        if not text:
            return text
        if text.endswith("()"):
            text = text[:-2]
        if "()." in text:
            text = text.split("().", 1)[0]
        if "." in text:
            return text
        return same_file.get(text) or all_by_name.get(text) or text


class Neo4jSchema:
    @staticmethod
    def constraints() -> list[str]:
        return [
            # Only Symbol has true unique constraint
            "CREATE CONSTRAINT symbol_qname_unique IF NOT EXISTS FOR (s:Symbol) REQUIRE s.qualified_name IS UNIQUE",
        ]

    @staticmethod
    def indexes() -> list[str]:
        return [
            "CREATE INDEX symbol_name_index IF NOT EXISTS FOR (s:Symbol) ON (s.name)",
            "CREATE INDEX symbol_repo_index IF NOT EXISTS FOR (s:Symbol) ON (s.repo)",
            "CREATE INDEX file_language_index IF NOT EXISTS FOR (f:File) ON (f.language)",
            "CREATE INDEX file_repo_index IF NOT EXISTS FOR (f:File) ON (f.repo)",
            "CREATE INDEX symbol_type_index IF NOT EXISTS FOR (s:Symbol) ON (s.type)",
        ]


class IngestQueries:
    UPSERT_FILES = """
    UNWIND $files AS file
    MERGE (f:File {repo: file.repo, path: file.path})
    SET f.language = file.language,
        f.hash = file.hash,
        f.lines_of_code = file.lines_of_code,
        f.is_test = file.is_test,
        f.last_indexed = datetime()
    """

    UPSERT_SYMBOLS = """
    UNWIND $symbols AS symbol
    MERGE (s:Symbol {qualified_name: symbol.qualified_name})
    SET s.repo = symbol.repo,
        s.name = symbol.name,
        s.type = symbol.type,
        s.start_line = symbol.start_line,
        s.end_line = symbol.end_line,
        s.file_path = symbol.file_path,
        s.is_test = symbol.is_test
    """

    UPSERT_PACKAGES = """
    UNWIND $packages AS pkg
    MERGE (p:Package {repo: pkg.repo, name: pkg.name})
    SET p.is_external = pkg.is_external,
        p.is_builtin = pkg.is_builtin
    """

    CREATE_CONTAINS = """
    UNWIND $rels AS rel
    MATCH (f:File {repo: rel.repo, path: rel.from})
    MATCH (s:Symbol {qualified_name: rel.to})
    MERGE (f)-[:CONTAINS]->(s)
    """

    CREATE_CALLS = """
    UNWIND $rels AS rel
    MATCH (caller:Symbol {qualified_name: rel.from})
    MATCH (callee:Symbol {qualified_name: rel.to})
    MERGE (caller)-[:CALLS]->(callee)
    """

    CREATE_IMPORTS = """
    UNWIND $rels AS rel
    MATCH (s:Symbol {qualified_name: rel.from})
    MATCH (p:Package {repo: rel.repo, name: rel.to})
    MERGE (s)-[:IMPORTS]->(p)
    """
