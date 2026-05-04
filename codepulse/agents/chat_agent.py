"""
Conversational Q&A agent over the code graph.

Accepts a plain-English question about the indexed codebase and returns
an answer backed by blast-radius data and LLM reasoning.

Falls back to a template answer if ANTHROPIC_API_KEY is not set.
"""

from __future__ import annotations

import os

from codepulse.graph.queries import get_blast_radius, get_test_coverage

_SYSTEM_PROMPT = """\
You are CodePulse, an expert code intelligence assistant.
You have access to a code knowledge graph.
Answer the user's question concisely and accurately based on the provided context.
If you don't know the answer from the context, say so honestly.
"""


def _call_llm(question: str, context: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_answer(question, context)

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Graph context:\n{context}\n\nQuestion: {question}",
            }
        ],
    )
    return message.content[0].text.strip()


def _fallback_answer(question: str, context: str) -> str:
    return (
        f"(LLM unavailable — set ANTHROPIC_API_KEY for full answers)\n"
        f"Context gathered:\n{context}"
    )


def answer(question: str, symbol_hint: str | None = None) -> str:
    """
    Answer *question* about the codebase.

    If *symbol_hint* is provided, enriches the context with blast-radius
    and test-coverage data for that symbol.
    """
    context_lines: list[str] = []

    if symbol_hint:
        impacted = get_blast_radius(symbol_hint)
        has_tests = get_test_coverage(symbol_hint)
        context_lines.append(f"Symbol: {symbol_hint}")
        context_lines.append(f"Has test coverage: {has_tests}")
        if impacted:
            context_lines.append("Downstream symbols:")
            for sym in impacted:
                context_lines.append(
                    f"  - {sym['name']} ({sym['kind']}) in {sym['file']} [depth {sym['depth']}]"
                )
        else:
            context_lines.append("No downstream symbols found in the graph.")

    context = "\n".join(context_lines) if context_lines else "No symbol context provided."
    return _call_llm(question, context)
