"""Graph schema and mapping helpers for Neo4j ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RepoNode:
    """Repository node in Neo4j."""
    id: str
    name: str
    path: str
    latest_commit_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoNode":
        return cls(
            id=data.get("repo_id", ""),
            name=data.get("repo_name", ""),
            path=data.get("root", ""),
            latest_commit_id=data.get("commit_id"),
        )


@dataclass(frozen=True)
class CommitNode:
    id: str
    repo_id: str
    mode: str
    base_commit: str | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommitNode | None":
        commit_id = data.get("commit_id")
        repo_id = data.get("repo_id")
        if not commit_id or not repo_id:
            return None
        return cls(
            id=str(commit_id),
            repo_id=str(repo_id),
            mode=str(data.get("mode", "commit")),
            base_commit=data.get("base_commit"),
        )


@dataclass(frozen=True)
class ChangeNode:
    repo_id: str
    commit_id: str
    file_path: str
    type: str
    status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, repo_id: str, commit_id: str) -> "ChangeNode":
        return cls(
            repo_id=str(data.get("repo_id", repo_id)),
            commit_id=str(data.get("commit_id", commit_id)),
            file_path=str(data.get("file_path", "")),
            type=str(data.get("type", "modified")),
            status=str(data.get("status", "M")),
        )


@dataclass(frozen=True)
class FileNode:
    repo_id: str
    commit_id: str
    repo: str
    path: str
    language: str
    hash: str
    lines_of_code: int = 0
    is_test: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileNode":
        max_line = max((s.get("end_line", 0) for s in data.get("symbols", [])), default=0)
        path = str(data.get("path", ""))
        repo = str(data.get("repo", ""))
        return cls(
            repo_id=data.get("repo_id", ""),
            commit_id=str(data.get("commit_id") or ""),
            repo=repo,
            path=path,
            language=str(data.get("language", "")),
            hash=str(data.get("hash", "")),
            lines_of_code=max_line,
            is_test="test" in path.lower(),
        )


@dataclass(frozen=True)
class SymbolNode:
    repo_id: str
    commit_id: str
    repo: str
    name: str
    qualified_name: str
    type: str
    start_line: int
    end_line: int
    file_path: str
    is_test: bool = False
    deleted: bool = False
    deleted_in_commit: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], file_path: str) -> "SymbolNode":
        name = str(data.get("name", ""))
        qualified_name = str(data.get("qualified_name", ""))
        # qualified_name is now prefixed with repo_id; use the explicit
        # `repo` field for the human-readable name.
        repo = str(data.get("repo", ""))
        return cls(
            repo_id=data.get("repo_id", repo),
            commit_id=str(data.get("commit_id") or ""),
            repo=repo,
            name=name,
            qualified_name=qualified_name,
            type=str(data.get("type", "")),
            start_line=int(data.get("start_line", 0)),
            end_line=int(data.get("end_line", 0)),
            file_path=file_path,
            is_test=name.startswith("test_") or "test" in file_path.lower(),
            deleted=bool(data.get("deleted", False)),
            deleted_in_commit=data.get("deleted_in_commit"),
        )


@dataclass(frozen=True)
class PackageNode:
    repo_id: str
    commit_id: str
    repo: str
    name: str
    is_external: bool = True
    is_builtin: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageNode":
        name = data.get("name", "")
        return cls(
            repo_id=data.get("repo_id", ""),
            commit_id=str(data.get("commit_id") or ""),
            repo=data.get("repo", ""),
            name=name,
            is_external=data.get("is_external", True),
            is_builtin=name in _PYTHON_STDLIB,
        )


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
    def extract_repo_node(json_data: dict[str, Any]) -> RepoNode | None:
        """Extract the Repo node from JSON data."""
        if not json_data.get("repo_id"):
            return None
        return RepoNode.from_dict(json_data)

    @staticmethod
    def extract_commit_node(json_data: dict[str, Any]) -> CommitNode | None:
        return CommitNode.from_dict(json_data)

    @staticmethod
    def extract_change_nodes(json_data: dict[str, Any]) -> list[ChangeNode]:
        repo_id = str(json_data.get("repo_id", ""))
        commit_id = str(json_data.get("commit_id", ""))
        nodes: list[ChangeNode] = []
        for change in json_data.get("changes", []):
            node = ChangeNode.from_dict(change, repo_id=repo_id, commit_id=commit_id)
            if node.file_path:
                nodes.append(node)
        return nodes

    @staticmethod
    def extract_file_nodes(json_data: dict[str, Any]) -> list[FileNode]:
        json_data.setdefault("repo_id", json_data.get("repo_name", ""))
        for result in json_data.get("results", []):
            result.setdefault("repo", json_data.get("repo_name", ""))
            result.setdefault("repo_id", json_data.get("repo_id", ""))
            result.setdefault("commit_id", json_data.get("commit_id", ""))
        return [FileNode.from_dict(result) for result in json_data.get("results", [])]

    @staticmethod
    def extract_symbol_nodes(json_data: dict[str, Any]) -> list[SymbolNode]:
        json_data.setdefault("repo_id", json_data.get("repo_name", ""))
        nodes: list[SymbolNode] = []
        for result in json_data.get("results", []):
            file_path = str(result.get("path", ""))
            for symbol in result.get("symbols", []):
                symbol.setdefault("repo_id", result.get("repo_id", json_data.get("repo_id", "")))
                symbol.setdefault("commit_id", result.get("commit_id", json_data.get("commit_id", "")))
                symbol.setdefault("repo", result.get("repo", json_data.get("repo_name", "")))
                nodes.append(SymbolNode.from_dict(symbol, file_path))
        return nodes

    @staticmethod
    def extract_package_nodes(json_data: dict[str, Any]) -> list[PackageNode]:
        repo_name = json_data.get("repo_name", "")
        repo_id = json_data.get("repo_id", repo_name)
        commit_id = json_data.get("commit_id", "")
        packages: dict[str, PackageNode] = {}
        for result in json_data.get("results", []):
            for symbol in result.get("symbols", []):
                for import_str in symbol.get("imports", []):
                    module_name = parse_import_statement(str(import_str))
                    if not module_name or module_name in packages:
                        continue
                    root_module = module_name.split(".", 1)[0]
                    packages[module_name] = PackageNode(
                        repo_id=repo_id,
                        commit_id=commit_id,
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
        repo_id = json_data.get("repo_id", repo_name)
        commit_id = json_data.get("commit_id", "")
        for result in json_data.get("results", []):
            file_path = str(result.get("path", ""))
            for symbol in result.get("symbols", []):
                rels.append({"repo_id": repo_id, "commit_id": commit_id, "repo": repo_name, "from": file_path, "to": str(symbol.get("qualified_name", ""))})
        return rels

    @staticmethod
    def extract_calls_relationships(json_data: dict[str, Any]) -> list[dict[str, Any]]:
        json_data.setdefault("repo_id", json_data.get("repo_name", ""))
        all_symbols = GraphMapper.extract_symbol_nodes(json_data)
        known = {symbol.qualified_name for symbol in all_symbols}
        by_name: dict[str, str] = {}
        for symbol in all_symbols:
            by_name.setdefault(symbol.name, symbol.qualified_name)

        repo_id = json_data.get("repo_id", "")
        commit_id = json_data.get("commit_id", "")
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
                        "repo_id": repo_id,
                        "commit_id": commit_id,
                        "from": caller,
                        "to": resolved,
                        "resolved": resolved in known,
                    })
        return rels

    @staticmethod
    def extract_imports_relationships(json_data: dict[str, Any]) -> list[dict[str, str]]:
        repo_name = json_data.get("repo_name", "")
        repo_id = json_data.get("repo_id", repo_name)
        commit_id = json_data.get("commit_id", "")
        rels: list[dict[str, str]] = []
        for result in json_data.get("results", []):
            for symbol in result.get("symbols", []):
                caller = str(symbol.get("qualified_name", ""))
                for import_str in symbol.get("imports", []):
                    module_name = parse_import_statement(str(import_str))
                    if module_name:
                        rels.append({"repo_id": repo_id, "commit_id": commit_id, "repo": repo_name, "from": caller, "to": module_name})
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
            "CREATE CONSTRAINT commit_repo_id_unique IF NOT EXISTS FOR (c:Commit) REQUIRE (c.repo_id, c.id) IS UNIQUE",
            "CREATE CONSTRAINT change_repo_commit_file_unique IF NOT EXISTS FOR (c:Change) REQUIRE (c.repo_id, c.commit_id, c.file_path) IS UNIQUE",
            "CREATE CONSTRAINT file_repo_commit_path_unique IF NOT EXISTS FOR (f:File) REQUIRE (f.repo_id, f.commit_id, f.path) IS UNIQUE",
            "CREATE CONSTRAINT symbol_repo_commit_qname_unique IF NOT EXISTS FOR (s:Symbol) REQUIRE (s.repo_id, s.commit_id, s.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT package_repo_commit_name_unique IF NOT EXISTS FOR (p:Package) REQUIRE (p.repo_id, p.commit_id, p.name) IS UNIQUE",
        ]

    @staticmethod
    def indexes() -> list[str]:
        return [
            # Repo-specific indexes for performance
            "CREATE INDEX symbol_repo_commit_name IF NOT EXISTS FOR (s:Symbol) ON (s.repo_id, s.commit_id, s.name)",
            "CREATE INDEX symbol_repo_file_deleted IF NOT EXISTS FOR (s:Symbol) ON (s.repo_id, s.file_path, s.deleted)",
            "CREATE INDEX file_repo_commit_path IF NOT EXISTS FOR (f:File) ON (f.repo_id, f.commit_id, f.path)",
            "CREATE INDEX package_repo_commit_name IF NOT EXISTS FOR (p:Package) ON (p.repo_id, p.commit_id, p.name)",
            "CREATE INDEX repo_id IF NOT EXISTS FOR (r:Repo) ON (r.id)",
            "CREATE INDEX commit_repo_id IF NOT EXISTS FOR (c:Commit) ON (c.repo_id, c.id)",
            "CREATE INDEX change_repo_commit_type IF NOT EXISTS FOR (c:Change) ON (c.repo_id, c.commit_id, c.type)",
            # Language/type indexes
            "CREATE INDEX file_language IF NOT EXISTS FOR (f:File) ON (f.language)",
            "CREATE INDEX symbol_type IF NOT EXISTS FOR (s:Symbol) ON (s.type)",
        ]


class IngestQueries:
    UPSERT_REPO = """
    UNWIND $repo AS r
    MERGE (repo:Repo {id: r.repo_id})
    SET repo.name = r.repo_name,
        repo.path = r.root,
        repo.latest_commit_id = r.latest_commit_id,
        repo.last_indexed = datetime()
    """

    UPSERT_COMMIT = """
    UNWIND $commits AS c
    MERGE (commit:Commit {repo_id: c.repo_id, id: c.id})
    SET commit.mode = c.mode,
        commit.base_commit = c.base_commit,
        commit.ingested_at = datetime()
    WITH commit, c
    MATCH (r:Repo {id: c.repo_id})
    MERGE (r)-[:HAS_COMMIT]->(commit)
    """

    UPSERT_CHANGES = """
    UNWIND $changes AS ch
    MERGE (c:Change {repo_id: ch.repo_id, commit_id: ch.commit_id, file_path: ch.file_path})
    SET c.type = ch.type,
        c.status = ch.status,
        c.updated_at = datetime()
    WITH c, ch
    MATCH (commit:Commit {repo_id: ch.repo_id, id: ch.commit_id})
    MERGE (commit)-[:HAS_CHANGE]->(c)
    """

    UPSERT_FILES = """
    UNWIND $files AS file
    MERGE (f:File {repo_id: file.repo_id, commit_id: file.commit_id, path: file.path})
    SET f.repo = file.repo,
        f.language = file.language,
        f.hash = file.hash,
        f.lines_of_code = file.lines_of_code,
        f.is_test = file.is_test,
        f.deleted = false,
        f.deleted_in_commit = null,
        f.last_indexed = datetime()
    WITH f, file
    MATCH (r:Repo {id: file.repo_id})
    MERGE (r)-[:CONTAINS]->(f)
    """

    UPSERT_SYMBOLS = """
    UNWIND $symbols AS symbol
    MERGE (s:Symbol {repo_id: symbol.repo_id, commit_id: symbol.commit_id, qualified_name: symbol.qualified_name})
    SET s.repo = symbol.repo,
        s.name = symbol.name,
        s.type = symbol.type,
        s.start_line = symbol.start_line,
        s.end_line = symbol.end_line,
        s.file_path = symbol.file_path,
        s.is_test = symbol.is_test,
        s.deleted = false,
        s.deleted_in_commit = null
    """

    UPSERT_PACKAGES = """
    UNWIND $packages AS pkg
    MERGE (p:Package {repo_id: pkg.repo_id, commit_id: pkg.commit_id, name: pkg.name})
    SET p.repo = pkg.repo,
        p.is_external = pkg.is_external,
        p.is_builtin = pkg.is_builtin
    """

    CREATE_CONTAINS = """
    UNWIND $rels AS rel
    MATCH (f:File {repo_id: rel.repo_id, commit_id: rel.commit_id, path: rel.from})
    MATCH (s:Symbol {repo_id: rel.repo_id, commit_id: rel.commit_id, qualified_name: rel.to})
    MERGE (f)-[:CONTAINS]->(s)
    """

    CREATE_CALLS = """
    UNWIND $rels AS rel
    MATCH (caller:Symbol {repo_id: rel.repo_id, commit_id: rel.commit_id, qualified_name: rel.from})
    MATCH (callee:Symbol {repo_id: rel.repo_id, commit_id: rel.commit_id, qualified_name: rel.to})
    MERGE (caller)-[:CALLS]->(callee)
    """

    CREATE_IMPORTS = """
    UNWIND $rels AS rel
    MATCH (s:Symbol {repo_id: rel.repo_id, commit_id: rel.commit_id, qualified_name: rel.from})
    MATCH (p:Package {repo_id: rel.repo_id, commit_id: rel.commit_id, name: rel.to})
    MERGE (s)-[:IMPORTS]->(p)
    """

    TOMBSTONE_DELETED_SYMBOLS = """
    UNWIND $changes AS ch
    WITH ch WHERE ch.type = 'deleted'
    MATCH (s:Symbol {repo_id: ch.repo_id, file_path: ch.file_path})
    WHERE coalesce(s.deleted, false) = false
    SET s.deleted = true,
        s.deleted_in_commit = ch.commit_id
    """
