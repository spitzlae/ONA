"""
3-Stufen-Suche: SuperLexikon DB → Web-Crawler → Groq LLM.

Jede gefundene Antwort wird automatisch in die DB zurückgeschrieben,
sodass das Lexikon mit jedem Rätsel wächst.
"""

from pathlib import Path
from kreuzwort.lexikon.db import load_cache, add_question, update_answers, get_missing_questions
from kreuzwort.lexikon.crawler import crawl_answers
from kreuzwort.lexikon.groq_fallback import ask_groq


class LexikonLookup:
    """
    Verwaltet die 3-Stufen-Suche und den In-Memory-Cache.

    Verwendung:
        lookup = LexikonLookup()
        answers, source = lookup.get_answers("Bedrängnis", 3)
    """

    def __init__(self, db_path: Path = None, use_crawler: bool = True,
                 use_groq: bool = True):
        self.db_path = db_path
        self.use_crawler = use_crawler
        self.use_groq = use_groq
        self.cache = load_cache(db_path)
        self.stats = {'db': 0, 'crawler': 0, 'groq': 0, 'none': 0}

    def get_answers(self, frage: str, laenge: int) -> tuple[list[str], str]:
        """
        Sucht Antworten in 3 Stufen.

        Returns:
            (antworten, quelle) wobei quelle 'DB', 'Crawler', 'Groq' oder 'None' ist.
        """
        q_key = frage.lower().strip()

        # Stufe 1: SuperLexikon Cache
        if q_key in self.cache:
            filtered = [a for a in self.cache[q_key] if len(a) == laenge]
            if filtered:
                self.stats['db'] += 1
                return filtered, 'DB'

        # Stufe 2: Web-Crawler
        if self.use_crawler:
            answers = crawl_answers(frage, laenge)
            if answers:
                self._save_to_cache(q_key, answers)
                self.stats['crawler'] += 1
                return answers, 'Crawler'

        # Stufe 3: Groq LLM
        if self.use_groq:
            answers = ask_groq(frage, laenge)
            if answers:
                self._save_to_cache(q_key, answers)
                self.stats['groq'] += 1
                return answers, 'Groq'

        self.stats['none'] += 1
        return [], 'None'

    def _save_to_cache(self, q_key: str, answers: list[str]):
        """Speichert neue Antworten im In-Memory-Cache."""
        if q_key in self.cache:
            # Bestehende Antworten ergänzen
            existing = set(self.cache[q_key])
            existing.update(answers)
            self.cache[q_key] = list(existing)
        else:
            self.cache[q_key] = answers

    def get_stats(self) -> dict:
        """Gibt Statistiken über die Suche zurück."""
        return dict(self.stats)
