"""
C / C++ parser using tree-sitter.

Extracts class / struct / enum / namespace definitions,
functions, methods, #include directives, and function calls
from C and C++ source files.
"""

from __future__ import annotations

import tree_sitter_cpp as ts_cpp
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
_LANGUAGE = Language(ts_cpp.language())
_parser = Parser(_LANGUAGE)

# Node types that represent a function scope in C/C++
_FUNCTION_NODES = {"function_definition"}


class CppParser(BaseParser):
    """Parse C / C++ source files into a ParseResult."""

    def parse(self, source: bytes, file_info: FileInfo) -> ParseResult:
        tree = _parser.parse(source)
        root = tree.root_node

        symbols = self._extract_symbols(root, source)
        imports = self._extract_includes(root, source)
        calls = self._extract_calls(root, source)
        exports = self._extract_exports(symbols, file_info)

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
        Collect function definitions, class / struct specifiers,
        namespace definitions, and enum specifiers.
        """
        symbols: list[SymbolInfo] = []

        for node in self._walk(root):
            if node.type == "function_definition":
                name = self._get_function_name(node, source)
                if name:
                    parent = self._find_enclosing_scope(node)
                    kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=kind,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

            elif node.type == "class_specifier":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_scope(node),
                    ))

            elif node.type == "struct_specifier":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.STRUCT,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_scope(node),
                    ))

            elif node.type == "namespace_definition":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.NAMESPACE,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=None,
                    ))

            elif node.type == "enum_specifier":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.ENUM,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=self._find_enclosing_scope(node),
                    ))

        return symbols

    # ── Include extraction ────────────────────────────────────

    def _extract_includes(self, root, source: bytes) -> list[ImportInfo]:
        """
        Extract #include directives.

        Maps both forms to ImportInfo:
            #include <iostream>    → module="iostream"
            #include "myheader.h" → module="myheader.h"
        """
        imports: list[ImportInfo] = []

        for node in self._walk(root):
            if node.type == "preproc_include":
                path_node = node.child_by_field_name("path")
                if path_node:
                    raw = self._node_text(path_node, source)
                    # Strip surrounding <>, "", or spaces
                    module = raw.strip("<>\"' ")
                    imports.append(ImportInfo(module=module, name=module))

        return imports

    # ── Call extraction ───────────────────────────────────────

    def _extract_calls(self, root, source: bytes) -> list[CallInfo]:
        """
        Collect function and method calls (call_expression nodes).
        """
        calls: list[CallInfo] = []

        for node in self._walk(root):
            if node.type == "call_expression":
                callee = self._get_callee_name(node, source)
                if not callee:
                    continue
                caller = self._find_enclosing_function(node, _FUNCTION_NODES)
                calls.append(CallInfo(
                    caller=caller or "<global>",
                    callee=callee,
                    line=node.start_point[0] + 1,
                ))

        return calls

    # ── Export extraction ─────────────────────────────────────

    def _extract_exports(
        self, symbols: list[SymbolInfo], file_info: FileInfo
    ) -> list[ExportInfo]:
        """
        Header files (.h, .hpp, .hxx) expose all top-level symbols.
        Source files (.cpp, .cc, .c) expose only top-level functions.
        """
        is_header = file_info.path.endswith((".h", ".hpp", ".hxx"))

        return [
            ExportInfo(name=s.name, kind=s.kind)
            for s in symbols
            if is_header or (
                s.parent is None and s.kind == SymbolKind.FUNCTION
            )
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

    def _get_function_name(self, node, source: bytes) -> str | None:
        """
        Extract function / method name from a function_definition.

        The C++ grammar nests the name inside a chain of declarators:
            function_definition
              ├─ type: ...
              └─ declarator: function_declarator
                   └─ declarator: (qualified_identifier | identifier)
        """
        declarator = node.child_by_field_name("declarator")
        if declarator is None:
            return None
        return self._extract_declarator_name(declarator, source)

    def _extract_declarator_name(self, node, source: bytes) -> str | None:
        """Recursively drill into declarator nodes to find the name."""
        # Base cases
        if node.type == "identifier":
            return self._node_text(node, source)

        if node.type == "field_identifier":
            return self._node_text(node, source)

        if node.type == "qualified_identifier":
            # MyClass::method → return just "method"
            name_node = node.child_by_field_name("name")
            if name_node:
                return self._node_text(name_node, source)

        # Recursive cases — unwrap wrapper declarators
        if node.type in (
            "function_declarator",
            "pointer_declarator",
            "reference_declarator",
        ):
            inner = node.child_by_field_name("declarator")
            if inner:
                return self._extract_declarator_name(inner, source)

        return None

    @staticmethod
    def _find_enclosing_scope(node) -> str | None:
        """Find the nearest enclosing class, struct, or namespace."""
        current = node.parent
        while current is not None:
            if current.type in ("class_specifier", "struct_specifier"):
                name = current.child_by_field_name("name")
                if name:
                    return name.text.decode("utf-8", errors="replace")
            elif current.type == "namespace_definition":
                name = current.child_by_field_name("name")
                if name:
                    return name.text.decode("utf-8", errors="replace")
            current = current.parent
        return None

    def _get_callee_name(self, node, source: bytes) -> str | None:
        """
        Extract the callee name from a call_expression.

        Handles:
            foo()            → "foo"
            obj.bar()        → "obj.bar"
            ns::func()       → "ns::func"
            this->method()   → "method"
            ptr->doStuff()   → "ptr->doStuff"
        """
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return None

        # Simple function call: foo()
        if func_node.type == "identifier":
            return self._node_text(func_node, source)

        # Qualified call: ns::func()
        if func_node.type == "qualified_identifier":
            return self._node_text(func_node, source)

        # Member access: obj.bar() or ptr->method()
        if func_node.type == "field_expression":
            argument = func_node.child_by_field_name("argument")
            field = func_node.child_by_field_name("field")
            if argument and field:
                arg_text = self._node_text(argument, source)
                field_text = self._node_text(field, source)
                # Simplify this->method → method
                if arg_text == "this":
                    return field_text
                return f"{arg_text}.{field_text}"

        # Template function: func<T>()
        if func_node.type == "template_function":
            name = func_node.child_by_field_name("name")
            if name:
                return self._node_text(name, source)

        # Fallback: return the raw text
        return self._node_text(func_node, source)
