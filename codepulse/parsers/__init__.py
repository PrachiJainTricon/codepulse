"""
Parser registry — maps Language enum to parser instances.

Parsers are lazily loaded so tree-sitter grammars are only
imported when actually needed.
"""

from codepulse.parsers.base import BaseParser, Language

# Lazily populated parser cache
_registry: dict[Language, BaseParser] = {}


def get_parser(language: Language) -> BaseParser:
    """
    Return the parser instance for the given language.

    Parsers are instantiated once and reused (they are stateless).
    """
    if language not in _registry:
        _registry[language] = _create_parser(language)
    return _registry[language]


def _create_parser(language: Language) -> BaseParser:
    """Lazy-load and instantiate the appropriate parser."""
    if language == Language.PYTHON:
        from codepulse.parsers.python_parser import PythonParser
        return PythonParser()

    if language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        from codepulse.parsers.typescript_parser import TypeScriptParser
        return TypeScriptParser()

    if language == Language.JAVA:
        from codepulse.parsers.java_parser import JavaParser
        return JavaParser()

    if language == Language.CPP:
        from codepulse.parsers.cpp_parser import CppParser
        return CppParser()

    raise ValueError(f"No parser available for {language}")
