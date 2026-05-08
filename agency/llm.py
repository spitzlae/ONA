"""
LLM-Abstraktionsschicht — Groq (default) oder Claude (via build-cli).

Jeder Aufruf ist eine frische Instanz ohne geteilten Kontext.
"""

import os
from groq import Groq


def _get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_Roche")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY oder GROQ_Roche nicht gesetzt")
    return Groq(api_key=api_key)


def ask(system_prompt: str, user_prompt: str,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 2000) -> str:
    """
    Einzelner LLM-Aufruf mit frischem Kontext.

    Args:
        system_prompt: Rolle und Anweisungen für den Agenten
        user_prompt: Die eigentliche Aufgabe
        model: LLM-Modell
        temperature: Kreativität (0=deterministisch, 1=kreativ)
        max_tokens: Maximale Antwortlänge

    Returns:
        Antwort als String
    """
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
