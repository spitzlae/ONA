"""
Claude Sonnet Fallback — fragt Claude via Roche AI Gateway.

Nutzt build-cli auth token für die Authentifizierung.
Funktioniert nur auf dem Laptop (WSL/Ubuntu) wo build-cli installiert ist.
"""

import subprocess
import requests

_PROXY_URL = "https://eu.build-cli.roche.com/proxy"
_MODEL = "claude-sonnet-4-6"


def _get_token() -> str | None:
    """Holt ein frisches Token von build-cli."""
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
    """Prüft ob build-cli verfügbar ist."""
    try:
        result = subprocess.run(
            ["build-cli", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def ask_claude(frage: str, laenge: int) -> list[str]:
    """
    Fragt Claude Sonnet nach Kreuzworträtsel-Lösungen.

    Args:
        frage: Die Rätsel-Frage
        laenge: Gewünschte Wortlänge

    Returns:
        Liste von Antworten in Großbuchstaben, oder leere Liste bei Fehler.
    """
    token = _get_token()
    if not token:
        return []

    try:
        response = requests.post(
            f"{_PROXY_URL}/v1/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": _MODEL,
                "max_tokens": 100,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Kreuzworträtsel-Lösung.\n"
                        f"Hinweis: '{frage}'\n"
                        f"Länge: {laenge} Buchstaben\n"
                        f"Gib ALLE möglichen deutschen Wörter (komma-separiert).\n"
                        f"Nur Wörter, keine Erklärungen. Umlaute als AE/OE/UE."
                    ),
                }],
            },
            timeout=15,
        )

        if response.status_code != 200:
            return []

        data = response.json()
        raw = data.get("content", [{}])[0].get("text", "")

        answers = []
        for part in raw.split(','):
            clean = ''.join(c for c in part.strip() if c.isalpha()).upper()
            if clean and len(clean) == laenge and clean not in answers:
                answers.append(clean)

        return answers

    except Exception:
        return []
