"""
LLM-Abstraktionsschicht — Claude via Roche AI Gateway (primary) oder Groq (fallback).

Jeder Aufruf ist eine frische Instanz ohne geteilten Kontext.
"""

import os
import subprocess
import requests
from groq import Groq

_PROXY_URL = "https://eu.build-cli.roche.com/proxy"
_CLAUDE_MODEL = "claude-sonnet-4-6"
_CUSTOM_HEADERS = {"x-build-cli-tool": "claude"}


def _get_token() -> str | None:
    try:
        result = subprocess.run(
            ["build-cli", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _has_build_cli() -> bool:
    try:
        result = subprocess.run(
            ["build-cli", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _ask_claude(system_prompt: str, user_prompt: str,
                temperature: float, max_tokens: int) -> str:
    token = _get_token()
    if not token:
        raise RuntimeError("build-cli auth token fehlgeschlagen")

    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(
                f"{_PROXY_URL}/v1/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    **_CUSTOM_HEADERS,
                },
                json={
                    "model": _CLAUDE_MODEL,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_error = e
            if attempt < 2:
                import time
                wait = 10 * (attempt + 1)
                print(f"  [Timeout] Retry in {wait}s... (Versuch {attempt + 2}/3)")
                time.sleep(wait)
    raise RuntimeError(f"Claude API nach 3 Versuchen fehlgeschlagen: {last_error}")


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
    Nutzt Claude (Roche AI Gateway) wenn build-cli verfügbar, sonst Groq.

    Args:
        system_prompt: Rolle und Anweisungen für den Agenten
        user_prompt: Die eigentliche Aufgabe
        model: Groq-Modell (wird ignoriert wenn Claude verwendet wird)
        temperature: Kreativität (0=deterministisch, 1=kreativ)
        max_tokens: Maximale Antwortlänge

    Returns:
        Antwort als String
    """
    if _has_build_cli():
        return _ask_claude(system_prompt, user_prompt, temperature, max_tokens)

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
