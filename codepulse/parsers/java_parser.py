"""
Java parser using tree-sitter.

Extracts class / interface / enum definitions, methods,
constructor declarations, import statements, method invocations,
and public exports from Java source files.
"""

from __future__ import annotations

import tree_sitter_java as ts_java
from tree_sitter import Language, Parser

from codepulse.parsers.base import (
    BaseParser,
    CallInfo,
    ExportInfo,
    FileInfo,
    ImportInfo,
    ParseResult,
    SymbolInfo,
    SymbolKind,
)

# ── Tree-sitter setup ────────────────────────────────────────
_LANGUAGE = Language(ts_java.language())
_parser = Parser(_LANGUAGE)

# Node types that represent a "function scope" in Java
_FUNCTION_NODES = {"method_declaration", "constructor_declaration"}


class JavaParser(BaseParser):
    """Parse Java source files into a ParseResult."""

    def parse(self, source: bytes, file_info: FileInfo) -> ParseResult:
        tree = _parser.parse(source)
        root = tree.root_node

        symbols = self._extract_symbols(root, source)
        imports = self._extract_imports(root, source)
        calls = self._extract_calls(root, source)
        exports = self._extract_exports(symbols)

        return ParseResult(
            file=file_info,
            symbols=symbols,
            imports=imports,
            calls=calls,
            exports=exports,
        )

    # ── Symbol extraction ─────────────────────────────────────

    def _extract_symbols(self, root, source: bytes) -> list[SymbolInfo]:
        """
        Walk the AST and collect class, interface, enum,
        method, and constructor definitions.
        """
        symbols: list[SymbolInfo] = []

        for node in self._walk(root):
            if node.type == "class_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_class(node),
                    ))

            elif node.type == "interface_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.INTERFACE,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_class(node),
                    ))

            elif node.type == "enum_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.ENUM,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_class(node),
                    ))

            elif node.type == "method_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    parent = self._find_enclosing_class(node)
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.METHOD,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

            elif node.type == "constructor_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    parent = self._find_enclosing_class(node)
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.CONSTRUCTOR,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

        return symbols

    # ── Import extraction ─────────────────────────────────────

    def _extract_imports(self, root, source: bytes) -> list[ImportInfo]:
        """
        Parse Java import declarations.

        Handles both regular and static imports:
            import java.util.List;
            import static java.util.Collections.*;
        """
        imports: list[ImportInfo] = []

        for node in self._walk(root):
            if node.type == "import_declaration":
                # Get the full text, e.g. "import java.util.List;"
                full_text = self._node_text(node, source).strip().rstrip(";")

                # Split into tokens: ["import", "java.util.List"]
                # or ["import", "static", "java.util.Collections.*"]
                parts = full_text.split()
                if len(parts) < 2:
                    continue

                # The actual dotted path is always the last token
                path = parts[-1]

                # Split into module (package) and name (class / wildcard)
                if "." in path:
                    module, name = path.rsplit(".", 1)
                else:
                    module = path
                    name = path

                imports.append(ImportInfo(module=module, name=name))

        return imports

    # ── Call extraction ───────────────────────────────────────

    def _extract_calls(self, root, source: bytes) -> list[CallInfo]:
        """
        Collect method invocations and constructor calls (new Foo()).
        """
        calls: list[CallInfo] = []

        for node in self._walk(root):
            if node.type == "method_invocation":
                callee = self._get_invocation_name(node, source)
                if not callee:
                    continue
                caller = self._find_enclosing_function(node, _FUNCTION_NODES)
                calls.append(CallInfo(
                    caller=caller or "<class>",
                    callee=callee,
                    line=node.start_point[0] + 1,
                ))

            elif node.type == "object_creation_expression":
                # new Foo() → treat as a constructor call
                type_node = node.child_by_field_name("type")
                if type_node:
                    callee = self._node_text(type_node, source)
                    caller = self._find_enclosing_function(node, _FUNCTION_NODES)
                    calls.append(CallInfo(
                        caller=caller or "<class>",
                        callee=f"new {callee}",
                        line=node.start_point[0] + 1,
                    ))

        return calls

    # ── Export extraction ─────────────────────────────────────

    def _extract_exports(self, symbols: list[SymbolInfo]) -> list[ExportInfo]:
        """
        In Java, top-level classes / interfaces / enums are the
        primary public API of a file.  We treat every top-level
        symbol as an export for the MVP.
        """
        return [
            ExportInfo(name=s.name, kind=s.kind)
            for s in symbols
            if s.parent is None
        ]

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _get_child_text(node, field_name: str, source: bytes) -> str | None:
        """Return the UTF-8 text of a named child field, or None."""
        child = node.child_by_field_name(field_name)
        if child is None:
            return None
        return source[child.start_byte:child.end_byte].decode(
            "utf-8", errors="replace"
        )

    @staticmethod
    def _find_enclosing_class(node) -> str | None:
        """Walk up the tree to find the nearest class / interface / enum name."""
        current = node.parent
        while current is not None:
            if current.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                name = current.child_by_field_name("name")
                if name:
                    return name.text.decode("utf-8", errors="replace")
            current = current.parent
        return None

    def _get_invocation_name(self, node, source: bytes) -> str | None:
        """
        Extract the callee name from a method_invocation node.

        Handles:
            foo()            → "foo"
            obj.bar()        → "obj.bar"
            this.baz()       → "baz"
            super.method()   → "super.method"
        """
        name_node = node.child_by_field_name("name")
        obj_node = node.child_by_field_name("object")

        if name_node is None:
            return None

        name = self._node_text(name_node, source)

        if obj_node:
            obj_text = self._node_text(obj_node, source)
            # Simplify this.method → method
            if obj_text == "this":
                return name
            return f"{obj_text}.{name}"

        return name
