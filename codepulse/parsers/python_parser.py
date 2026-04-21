"""
Python parser using tree-sitter.

Extracts symbols (classes, functions, methods), imports,
function calls, and exports from Python source files.

Supported patterns:
  - class definitions (including nested)
  - function / method / __init__ definitions
  - import & from-import (with aliases and wildcards)
  - function calls (simple, attribute, self.method)
  - exports: top-level public (no leading underscore) symbols
"""

from __future__ import annotations

import tree_sitter_python as ts_python
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
_LANGUAGE = Language(ts_python.language())
_parser = Parser(_LANGUAGE)

# Node types that represent a "function scope" in Python
_FUNCTION_NODES = {"function_definition", "class_definition"}


class PythonParser(BaseParser):
    """Parse Python source files into a ParseResult."""

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
        """Find all class and function definitions in the AST."""
        symbols: list[SymbolInfo] = []

        for node in self._walk(root):
            if node.type == "class_definition":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_function(
                            node, _FUNCTION_NODES
                        ),
                    ))

            elif node.type == "function_definition":
                name = self._get_child_text(node, "name", source)
                if name:
                    # Is this function inside a class? → method
                    parent = self._find_enclosing_class(node)
                    kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
                    # __init__ is a constructor
                    if name == "__init__":
                        kind = SymbolKind.CONSTRUCTOR
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=kind,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

        return symbols

    # ── Import extraction ─────────────────────────────────────

    def _extract_imports(self, root, source: bytes) -> list[ImportInfo]:
        """
        Parse import and from-import statements.

        Handles:
          import foo
          import foo as f
          from foo.bar import baz, qux
          from foo import *
        """
        imports: list[ImportInfo] = []

        for node in self._walk(root):
            if node.type == "import_statement":
                # import foo, bar
                for child in node.children:
                    if child.type == "dotted_name":
                        module = self._node_text(child, source)
                        imports.append(
                            ImportInfo(module=module, name=module)
                        )
                    elif child.type == "aliased_import":
                        dotted = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if dotted:
                            mod = self._node_text(dotted, source)
                            alias = (
                                self._node_text(alias_node, source)
                                if alias_node else None
                            )
                            imports.append(
                                ImportInfo(module=mod, name=mod, alias=alias)
                            )

            elif node.type == "import_from_statement":
                # from foo.bar import baz, qux
                module_node = node.child_by_field_name("module_name")
                module = (
                    self._node_text(module_node, source)
                    if module_node else ""
                )

                for child in node.children:
                    if child.type == "dotted_name" and child != module_node:
                        name = self._node_text(child, source)
                        imports.append(ImportInfo(module=module, name=name))

                    elif child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        if name_node:
                            name = self._node_text(name_node, source)
                            alias = (
                                self._node_text(alias_node, source)
                                if alias_node else None
                            )
                            imports.append(
                                ImportInfo(module=module, name=name, alias=alias)
                            )

                    elif child.type == "wildcard_import":
                        imports.append(ImportInfo(module=module, name="*"))

        return imports

    # ── Call extraction ───────────────────────────────────────

    def _extract_calls(self, root, source: bytes) -> list[CallInfo]:
        """
        Find all function / method calls and map each to its
        enclosing function scope.
        """
        calls: list[CallInfo] = []

        for node in self._walk(root):
            if node.type == "call":
                callee = self._get_callee_name(node, source)
                if not callee:
                    continue
                # Find enclosing function that contains this call
                caller = self._find_enclosing_function(
                    node, _FUNCTION_NODES
                )
                calls.append(CallInfo(
                    caller=caller or "<module>",
                    callee=callee,
                    line=node.start_point[0] + 1,
                ))

        return calls

    # ── Export extraction ─────────────────────────────────────

    def _extract_exports(self, symbols: list[SymbolInfo]) -> list[ExportInfo]:
        """
        In Python, top-level definitions that don't start with
        an underscore are considered public exports.
        """
        return [
            ExportInfo(name=s.name, kind=s.kind)
            for s in symbols
            if s.parent is None and not s.name.startswith("_")
        ]

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _get_child_text(
        node, field_name: str, source: bytes
    ) -> str | None:
        """Get text of a named child field, or None."""
        child = node.child_by_field_name(field_name)
        if child is None:
            return None
        return source[child.start_byte:child.end_byte].decode(
            "utf-8", errors="replace"
        )

    @staticmethod
    def _find_enclosing_class(node) -> str | None:
        """Walk up to find the nearest enclosing class name."""
        current = node.parent
        while current is not None:
            if current.type == "class_definition":
                name_node = current.child_by_field_name("name")
                if name_node:
                    return name_node.text.decode("utf-8", errors="replace")
            current = current.parent
        return None

    def _get_callee_name(self, node, source: bytes) -> str | None:
        """
        Extract the callee name from a call node.

        Handles:
          foo()           → "foo"
          self.bar()      → "bar"        (strips self.)
          obj.method()    → "obj.method"
          module.func()   → "module.func"
        """
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return None

        # Simple call: foo()
        if func_node.type == "identifier":
            return self._node_text(func_node, source)

        # Attribute call: obj.bar()
        if func_node.type == "attribute":
            obj_node = func_node.child_by_field_name("object")
            attr_node = func_node.child_by_field_name("attribute")
            if obj_node and attr_node:
                obj_text = self._node_text(obj_node, source)
                attr_text = self._node_text(attr_node, source)
                # self.method() → just "method"
                if obj_text == "self":
                    return attr_text
                return f"{obj_text}.{attr_text}"

        # Fallback: return raw text
        return self._node_text(func_node, source)
