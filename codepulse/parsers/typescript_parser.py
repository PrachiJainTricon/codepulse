"""
TypeScript & JavaScript parser using tree-sitter.

Extracts symbols, imports, calls, and exports from
.ts, .tsx, .js, .jsx, .mjs, .cjs files.

A single parser class handles both TypeScript and JavaScript
because their AST structures are nearly identical — the only
difference is the tree-sitter grammar used for parsing.

Supported patterns:
  - function declarations, class declarations, method definitions
  - arrow functions assigned to const / let
  - TypeScript: interface, enum declarations
  - ES6 imports + CommonJS require()
  - export statements (named, default, re-export)
  - call expressions (simple, member, this.method)

Node type constants (from source tree_parser.py):
  - JS/TS node types for import/class/method/function/call detection
"""

from __future__ import annotations

import tree_sitter_javascript as ts_javascript
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser

from codepulse.parsers.base import (
    BaseParser,
    CallInfo,
    ExportInfo,
    FileInfo,
    ImportInfo,
    Language as LangEnum,
    ParseResult,
    SymbolInfo,
    SymbolKind,
)

JS_TS_CLASS_TYPES = {"class_declaration"}
JS_TS_METHOD_TYPES = {"method_definition"}
JS_TS_FUNCTION_TYPES = {
    "function_declaration",
    "function_expression",
    "arrow_function",
}
JS_TS_CALL_TYPES = {"call_expression", "new_expression"}

# ── Tree-sitter language objects ──────────────────────────────
_JS_LANGUAGE = Language(ts_javascript.language())
_TS_LANGUAGE = Language(ts_typescript.language_typescript())
_TSX_LANGUAGE = Language(ts_typescript.language_tsx())

# One parser per language variant
_js_parser = Parser(_JS_LANGUAGE)
_ts_parser = Parser(_TS_LANGUAGE)
_tsx_parser = Parser(_TSX_LANGUAGE)

# Node types representing a function scope
_FUNCTION_NODES = {
    "function_declaration", "method_definition",
    "arrow_function", "function", "generator_function_declaration",
}


class TypeScriptParser(BaseParser):
    """Parse TypeScript / JavaScript files into a ParseResult."""

    def parse(self, source: bytes, file_info: FileInfo) -> ParseResult:
        parser = self._pick_parser(file_info)
        tree = parser.parse(source)
        root = tree.root_node

        symbols = self._extract_symbols(root, source)
        imports = self._extract_imports(root, source)
        calls = self._extract_calls(root, source)
        exports = self._extract_exports(root, source, symbols)

        return ParseResult(
            file=file_info,
            symbols=symbols,
            imports=imports,
            calls=calls,
            exports=exports,
        )

    # ── Parser selection ──────────────────────────────────────

    @staticmethod
    def _pick_parser(file_info: FileInfo) -> Parser:
        """Choose the right tree-sitter parser based on file extension."""
        path = file_info.path
        if path.endswith((".tsx", ".jsx")):
            return _tsx_parser
        if path.endswith(".ts"):
            return _ts_parser
        return _js_parser   # .js, .mjs, .cjs

    # ── Symbol extraction ─────────────────────────────────────

    def _extract_symbols(self, root, source: bytes) -> list[SymbolInfo]:
        """
        Walk the AST and collect function, class, method,
        interface, and enum declarations.
        """
        symbols: list[SymbolInfo] = []

        for node in self._walk(root):
            if node.type == "function_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    parent = self._find_enclosing_class_name(node)
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=(
                            SymbolKind.METHOD if parent
                            else SymbolKind.FUNCTION
                        ),
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

            elif node.type == "class_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.CLASS,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=None,
                    ))

            elif node.type == "method_definition":
                name = self._get_child_text(node, "name", source)
                if name:
                    parent = self._find_enclosing_class_name(node)
                    kind = (
                        SymbolKind.CONSTRUCTOR
                        if name == "constructor"
                        else SymbolKind.METHOD
                    )
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=kind,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=parent,
                    ))

            # Arrow function assigned to a variable:
            #   const foo = () => {}
            elif node.type == "lexical_declaration":
                for decl in node.children:
                    if decl.type == "variable_declarator":
                        value = decl.child_by_field_name("value")
                        if value and value.type in (
                            "arrow_function", "function"
                        ):
                            name_node = decl.child_by_field_name("name")
                            if name_node:
                                name = self._node_text(name_node, source)
                                symbols.append(SymbolInfo(
                                    name=name,
                                    kind=SymbolKind.FUNCTION,
                                    line=node.start_point[0] + 1,
                                    end_line=node.end_point[0] + 1,
                                    parent=None,
                                ))

            # TypeScript-specific: interface declarations
            elif node.type == "interface_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.INTERFACE,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=None,
                    ))

            # TypeScript-specific: enum declarations
            elif node.type == "enum_declaration":
                name = self._get_child_text(node, "name", source)
                if name:
                    symbols.append(SymbolInfo(
                        name=name,
                        kind=SymbolKind.ENUM,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=None,
                    ))

        return symbols

    # ── Import extraction ─────────────────────────────────────

    def _extract_imports(self, root, source: bytes) -> list[ImportInfo]:
        """
        Parse ES6 import statements and CommonJS require() calls.
        """
        imports: list[ImportInfo] = []

        for node in self._walk(root):
            if node.type == "import_statement":
                module = self._get_import_source(node, source)
                if not module:
                    continue
                # Walk the import clause to collect named imports,
                # default import, or namespace import
                for child in node.children:
                    if child.type == "import_clause":
                        self._parse_import_clause(
                            child, source, module, imports
                        )

            # CommonJS: const x = require("module")
            elif node.type == "call_expression":
                func = node.child_by_field_name("function")
                if func and self._node_text(func, source) == "require":
                    args = node.child_by_field_name("arguments")
                    if args and args.named_child_count > 0:
                        mod_node = args.named_children[0]
                        module = self._strip_quotes(
                            self._node_text(mod_node, source)
                        )
                        imports.append(
                            ImportInfo(module=module, name=module)
                        )

        return imports

    # ── Call extraction ───────────────────────────────────────

    def _extract_calls(self, root, source: bytes) -> list[CallInfo]:
        """Collect function / method calls (excluding require())."""
        calls: list[CallInfo] = []

        for node in self._walk(root):
            if node.type == "call_expression":
                callee = self._get_callee_name(node, source)
                # Skip require() — it's an import, not a call
                if not callee or callee == "require":
                    continue
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

    def _extract_exports(
        self,
        root,
        source: bytes,
        symbols: list[SymbolInfo],
    ) -> list[ExportInfo]:
        """
        Collect explicitly exported symbols.

        Handles:
          export function foo() {}
          export class Bar {}
          export { a, b }
          export default ...
        """
        exports: list[ExportInfo] = []
        exported_names: set[str] = set()

        for node in self._walk(root):
            if node.type == "export_statement":
                # Inline exports: export function foo() {}
                for child in node.children:
                    if child.type in (
                        "function_declaration", "class_declaration",
                        "interface_declaration", "enum_declaration",
                    ):
                        name = self._get_child_text(child, "name", source)
                        if name:
                            exported_names.add(name)

                # Re-export / named exports: export { a, b }
                clause = None
                for child in node.children:
                    if child.type == "export_clause":
                        clause = child
                        break
                if clause:
                    for spec in clause.children:
                        if spec.type == "export_specifier":
                            name_node = spec.child_by_field_name("name")
                            if name_node:
                                exported_names.add(
                                    self._node_text(name_node, source)
                                )

        # Map exported names back to symbols for kind info
        symbol_map = {s.name: s for s in symbols}
        for name in exported_names:
            sym = symbol_map.get(name)
            kind = sym.kind if sym else SymbolKind.VARIABLE
            exports.append(ExportInfo(name=name, kind=kind))

        return exports

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _get_child_text(
        node, field_name: str, source: bytes
    ) -> str | None:
        """Return the UTF-8 text of a named child field, or None."""
        child = node.child_by_field_name(field_name)
        if child is None:
            return None
        return source[child.start_byte:child.end_byte].decode(
            "utf-8", errors="replace"
        )

    @staticmethod
    def _find_enclosing_class_name(node) -> str | None:
        """Walk up to find the nearest enclosing class name."""
        current = node.parent
        while current is not None:
            if current.type == "class_declaration":
                name = current.child_by_field_name("name")
                if name:
                    return name.text.decode("utf-8", errors="replace")
            current = current.parent
        return None

    def _get_callee_name(self, node, source: bytes) -> str | None:
        """
        Extract callee name from a call_expression.

        Handles:
          foo()          → "foo"
          obj.bar()      → "obj.bar"
          this.method()  → "method"    (strips this.)
        """
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return None

        if func_node.type == "identifier":
            return self._node_text(func_node, source)

        if func_node.type == "member_expression":
            obj = func_node.child_by_field_name("object")
            prop = func_node.child_by_field_name("property")
            if obj and prop:
                obj_text = self._node_text(obj, source)
                prop_text = self._node_text(prop, source)
                # this.method → method
                if obj_text == "this":
                    return prop_text
                return f"{obj_text}.{prop_text}"

        # Fallback: raw text
        return self._node_text(func_node, source)

    @staticmethod
    def _get_import_source(node, source: bytes) -> str | None:
        """Extract the module path string from an import statement."""
        for child in node.children:
            if child.type == "string":
                raw = source[child.start_byte:child.end_byte].decode(
                    "utf-8", errors="replace"
                )
                return raw.strip("\"'`")
        return None

    def _parse_import_clause(
        self,
        node,
        source: bytes,
        module: str,
        imports: list[ImportInfo],
    ) -> None:
        """Recursively parse import clause children."""
        for child in node.children:
            # Default import: import foo from "module"
            if child.type == "identifier":
                name = self._node_text(child, source)
                imports.append(ImportInfo(module=module, name=name))

            # Named imports: import { a, b as c } from "module"
            elif child.type == "named_imports":
                for spec in child.children:
                    if spec.type == "import_specifier":
                        name_node = spec.child_by_field_name("name")
                        alias_node = spec.child_by_field_name("alias")
                        if name_node:
                            name = self._node_text(name_node, source)
                            alias = (
                                self._node_text(alias_node, source)
                                if alias_node else None
                            )
                            imports.append(
                                ImportInfo(
                                    module=module, name=name, alias=alias
                                )
                            )

            # Namespace import: import * as ns from "module"
            elif child.type == "namespace_import":
                for sub in child.children:
                    if sub.type == "identifier":
                        alias = self._node_text(sub, source)
                        imports.append(
                            ImportInfo(module=module, name="*", alias=alias)
                        )

    @staticmethod
    def _strip_quotes(text: str) -> str:
        """Remove surrounding quotes from a string literal."""
        return text.strip("\"'`")
