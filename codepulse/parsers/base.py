"""
Base dataclasses and abstract parser interface.

Every language parser produces a ParseResult, which is the
universal exchange format between the indexer and the graph writer.

Hierarchy:
    FileInfo        — metadata about the source file
    SymbolInfo      — one code symbol (function, class, method, …)
    ImportInfo      — one import / include statement
    CallInfo        — one caller → callee relationship
    ExportInfo      — one publicly visible symbol
    ParseResult     — all of the above for a single file
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


# ── Enums ────────────────────────────────────────────────────


class SymbolKind(str, Enum):
    """The kind of code symbol extracted from the AST."""
    FUNCTION    = "function"
    METHOD      = "method"
    CLASS       = "class"
    INTERFACE   = "interface"
    ENUM        = "enum"
    STRUCT      = "struct"
    NAMESPACE   = "namespace"
    VARIABLE    = "variable"
    CONSTRUCTOR = "constructor"


class Language(str, Enum):
    """Programming languages supported by codepulse parsers."""
    PYTHON     = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA       = "java"
    CPP        = "cpp"


# ── Dataclasses ──────────────────────────────────────────────


@dataclass(frozen=True)
class FileInfo:
    """Metadata about the source file being parsed."""
    path: str           # relative path from repo root
    language: Language
    hash: str           # sha-256 hex digest


@dataclass(frozen=True)
class SymbolInfo:
    """A single code symbol (function, class, method, …)."""
    name: str
    kind: SymbolKind
    line: int           # 1-based start line
    end_line: int       # 1-based end line
    parent: str | None = None   # enclosing symbol name, if any


@dataclass(frozen=True)
class ImportInfo:
    """A single import / include statement."""
    module: str         # the module or file being imported
    name: str           # the specific symbol imported (or "*")
    alias: str | None = None


@dataclass(frozen=True)
class CallInfo:
    """A function / method call relationship."""
    caller: str         # enclosing function ("<module>" if top-level)
    callee: str         # function / method being called
    line: int           # 1-based line of the call


@dataclass(frozen=True)
class ExportInfo:
    """A symbol that is exported / publicly visible."""
    name: str
    kind: SymbolKind


@dataclass
class ParseResult:
    """
    The complete parse output for one source file.

    This is the universal exchange format that every language
    parser must produce.  The graph writer consumes these to
    build Neo4j nodes and edges.
    """
    file: FileInfo
    symbols: list[SymbolInfo]   = field(default_factory=list)
    imports: list[ImportInfo]   = field(default_factory=list)
    calls:   list[CallInfo]     = field(default_factory=list)
    exports: list[ExportInfo]   = field(default_factory=list)


# ── Abstract base parser ─────────────────────────────────────


class BaseParser(ABC):
    """
    Contract every language parser must fulfil.

    Subclasses implement `parse()` which receives raw file bytes
    and file metadata, returning a fully-populated ParseResult.
    """

    @abstractmethod
    def parse(self, source: bytes, file_info: FileInfo) -> ParseResult:
        """
        Parse *source* bytes and return a structured ParseResult.

        Parameters
        ----------
        source : bytes
            Raw UTF-8 file content.
        file_info : FileInfo
            Pre-populated metadata (path, language, hash).

        Returns
        -------
        ParseResult
        """
        ...

    # ── Shared helpers available to all parsers ───────────────

    @staticmethod
    def _node_text(node, source: bytes) -> str:
        """Extract the UTF-8 text that a tree-sitter node spans."""
        return source[node.start_byte:node.end_byte].decode(
            "utf-8", errors="replace"
        )

    @staticmethod
    def _find_enclosing_function(
        node, function_node_types: set[str]
    ) -> str | None:
        """
        Walk up the AST from *node* and return the name of the
        nearest enclosing function / method, or None if at module level.
        """
        current = node.parent
        while current is not None:
            if current.type in function_node_types:
                # Grab the name child (works for most grammars)
                for child in current.children:
                    if child.type in (
                        "identifier", "name", "property_identifier",
                    ):
                        return child.text.decode("utf-8", errors="replace")
            current = current.parent
        return None

    @staticmethod
    def _walk(node):
        """Depth-first generator over every node in the subtree."""
        cursor = node.walk()
        visited = False
        while True:
            if not visited:
                yield cursor.node
                if cursor.goto_first_child():
                    continue
            if cursor.goto_next_sibling():
                visited = False
                continue
            if not cursor.goto_parent():
                break
            visited = True
