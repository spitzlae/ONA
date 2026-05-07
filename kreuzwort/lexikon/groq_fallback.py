"""
Groq LLM Fallback — fragt Llama nach Kreuzworträtsel-Lösungen.

Letzte Stufe der 3-Stufen-Suche, wenn DB und Crawler keine Antwort haben.
"""

from groq import Groq
from kreuzwort.config import GROQ_API_KEY

_client = None


def _get_client() -> Groq | None:
    """Lazy-Init des Groq-Clients."""
    global _client
    if _client is None and GROQ_API_KEY:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def ask_groq(frage: str, laenge: int) -> list[str]:
    """
    Fragt Groq/Llama nach Kreuzworträtsel-Lösungen.

    Args:
        frage: Die Rätsel-Frage
        laenge: Gewünschte Wortlänge

    Returns:
        Liste von Antworten in Großbuchstaben, oder leere Liste bei Fehler.
    """
    client = _get_client()
    if client is None:
        return []

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": (
                    f"Kreuzworträtsel-Lösung.\n"
                    f"Hinweis: '{frage}'\n"
                    f"Länge: {laenge} Buchstaben\n"
                    f"Gib ALLE möglichen deutschen Wörter (komma-separiert).\n"
                    f"Nur Wörter, keine Erklärungen."
                ),
            }],
            temperature=0.0,
            max_tokens=80,
        )

        raw = response.choices[0].message.content.strip()
        answers = []
        for part in raw.split(','):
            clean = ''.join(c for c in part.strip() if c.isalpha()).upper()
            if clean and len(clean) == laenge and clean not in answers:
                answers.append(clean)

        return answers

    except Exception:
        return []
