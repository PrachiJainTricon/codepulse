"""
Generic LLM client — provider-agnostic interface.

Supports: anthropic, openai (GPT), groq, gemini.
Configure via environment variables:
    CODEPULSE_LLM_PROVIDER  — one of: anthropic, openai, groq, gemini (default: anthropic)
    CODEPULSE_LLM_MODEL     — model name (auto-selected per provider if not set)
    ANTHROPIC_API_KEY       — for anthropic provider
    OPENAI_API_KEY          — for openai provider
    GROQ_API_KEY            — for groq provider
    GOOGLE_API_KEY          — for gemini provider
"""

from __future__ import annotations

import os


def _get_provider() -> str:
    return os.getenv("CODEPULSE_LLM_PROVIDER", "anthropic").lower()


def _get_model() -> str:
    explicit = os.getenv("CODEPULSE_LLM_MODEL")
    if explicit:
        return explicit
    # Sensible defaults per provider
    defaults = {
        "anthropic": "claude-3-5-haiku-20241022",
        "openai": "gpt-4o-mini",
        "groq": "llama-3.1-8b-instant",
        "gemini": "gemini-2.0-flash",
    }
    return defaults.get(_get_provider(), "claude-3-5-haiku-20241022")


def call_llm(*, system: str, user: str, max_tokens: int = 512) -> str:
    """
    Call the configured LLM provider.

    Raises EnvironmentError if the required API key is not set.
    """
    provider = _get_provider()

    if provider == "anthropic":
        return _call_anthropic(system, user, max_tokens)
    elif provider == "openai":
        return _call_openai(system, user, max_tokens)
    elif provider == "groq":
        return _call_groq(system, user, max_tokens)
    elif provider == "gemini":
        return _call_gemini(system, user, max_tokens)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Set CODEPULSE_LLM_PROVIDER to one of: anthropic, openai, groq, gemini"
        )


# ── Provider implementations ─────────────────────────────────────────────────

def _call_anthropic(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_get_model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def _call_openai(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=_get_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_groq(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY not set")

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=_get_model(),
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_gemini(system: str, user: str, max_tokens: int) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY not set")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_get_model(),
        contents=f"{system}\n\n{user}",
        config=genai.types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return response.text.strip()
