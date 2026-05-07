"""
Mehrstufige Suche mit OCR-Optimierung und DB-Persistierung.

Suchstrategie pro Frage:
  1. DB-Cache (SuperLexikon)
  2. Web-Crawler (mit bereinigtem Text)
  3. Claude/Groq LLM (mit bereinigtem Text)
  4. Claude/Groq Retry (mit optimiertem Text, falls Schritt 3 scheitert)

Jede gefundene Antwort wird in Cache UND SQLite-DB gespeichert,
sodass das Lexikon mit jedem Rätsel wächst.
"""

import re
from pathlib import Path
from kreuzwort.config import HAS_CLAUDE
from kreuzwort.lexikon.db import load_cache, add_question, update_answers, get_missing_questions
from kreuzwort.lexikon.crawler import crawl_answers
from kreuzwort.lexikon.groq_fallback import ask_groq
from kreuzwort.ocr_cleaning import clean_ocr_text


def _optimize_query(frage: str) -> str | None:
    """
    Versucht den Suchbegriff weiter zu optimieren für einen Retry.

    Gibt None zurück wenn keine sinnvolle Optimierung möglich ist.
    """
    optimized = frage

    # Abkürzungen auflösen
    optimized = re.sub(r'\bugs\.?\b', 'umgangssprachlich', optimized)
    optimized = re.sub(r'\babk\.?\b', 'abkürzung', optimized)
    optimized = re.sub(r'\bmz\.?\b', 'mehrzahl', optimized)
    optimized = re.sub(r'\bkw\.?\b', 'kurzwort', optimized)
    optimized = re.sub(r'\bfrz\.?\b', 'französisch', optimized)
    optimized = re.sub(r'\bengl\.?\b', 'englisch', optimized)
    optimized = re.sub(r'\bital\.?\b', 'italienisch', optimized)
    optimized = re.sub(r'\bspan\.?\b', 'spanisch', optimized)
    optimized = re.sub(r'\blat\.?\b', 'lateinisch', optimized)
    optimized = re.sub(r'\bgriech\.?\b', 'griechisch', optimized)
    optimized = re.sub(r'\btürk\.?\b', 'türkisch', optimized)
    optimized = re.sub(r'\bmed\.?\b', 'medizinisch', optimized)
    optimized = re.sub(r'\bbibl\.?\b', 'biblisch', optimized)
    optimized = re.sub(r'\bnordd\.?\b', 'norddeutsch', optimized)
    optimized = re.sub(r'\bsüdd\.?\b', 'süddeutsch', optimized)
    optimized = re.sub(r'\bösterr\.?\b', 'österreichisch', optimized)
    optimized = re.sub(r'\bschweiz\.?\b', 'schweizerisch', optimized)
    optimized = re.sub(r'\bind\.?\b', 'indisch', optimized)

    # Todessymbol klarer machen
    optimized = re.sub(r'†\s*(\d{4})', r'gestorben \1', optimized)

    # Nur zurückgeben wenn sich etwas geändert hat
    if optimized.strip() != frage.strip():
        return optimized.strip()

    return None


class LexikonLookup:
    """
    Verwaltet die mehrstufige Suche und den In-Memory-Cache.

    Verwendung:
        lookup = LexikonLookup()
        answers, source = lookup.get_answers("Bedrängnis", 3)
    """

    def __init__(self, db_path: Path = None, use_crawler: bool = True,
                 use_groq: bool = True, use_claude: bool = None):
        self.db_path = db_path
        self.use_crawler = use_crawler
        self.use_groq = use_groq
        self.use_claude = use_claude if use_claude is not None else HAS_CLAUDE
        self.cache = load_cache(db_path)
        self.stats = {'db': 0, 'crawler': 0, 'claude': 0, 'groq': 0, 'none': 0}

    def get_answers(self, frage: str, laenge: int,
                    source_image: int = 0) -> tuple[list[str], str]:
        """
        Sucht Antworten in mehreren Stufen mit OCR-Optimierung.

        Args:
            frage: Die Rätsel-Frage (kann OCR-Rohtext sein)
            laenge: Gewünschte Wortlänge
            source_image: Rätsel-Nummer für DB-Zuordnung

        Returns:
            (antworten, quelle) — quelle ist 'db', 'crawler', 'claude', 'groq' oder 'none'
        """
        # OCR-Cleaning auf den Suchbegriff anwenden
        frage_clean, _ = clean_ocr_text(frage)
        q_key = frage_clean.lower().strip()

        # Stufe 1: DB-Cache
        if q_key in self.cache:
            filtered = [a for a in self.cache[q_key] if len(a) == laenge]
            if filtered:
                self.stats['db'] += 1
                return filtered, 'db'

        # Stufe 2: Web-Crawler
        if self.use_crawler:
            answers = crawl_answers(frage_clean, laenge)
            if answers:
                self._save(q_key, answers, frage, laenge, source_image)
                self.stats['crawler'] += 1
                return answers, 'crawler'

        # Stufe 3: LLM (mit bereinigtem Text)
        answers, llm_source = self._ask_llm(frage_clean, laenge)
        if answers:
            self._save(q_key, answers, frage, laenge, source_image)
            self.stats[llm_source] += 1
            return answers, llm_source

        # Stufe 4: Retry mit optimiertem Suchbegriff
        optimized = _optimize_query(q_key)
        if optimized and optimized != q_key:
            # Erst DB prüfen mit optimiertem Key
            if optimized in self.cache:
                filtered = [a for a in self.cache[optimized] if len(a) == laenge]
                if filtered:
                    self._save(q_key, filtered, frage, laenge, source_image)
                    self.stats['db'] += 1
                    return filtered, 'db'

            # Crawler mit optimiertem Text
            if self.use_crawler:
                answers = crawl_answers(optimized, laenge)
                if answers:
                    self._save(q_key, answers, frage, laenge, source_image)
                    self.stats['crawler'] += 1
                    return answers, 'crawler'

            # LLM mit optimiertem Text
            answers, llm_source = self._ask_llm(optimized, laenge)
            if answers:
                self._save(q_key, answers, frage, laenge, source_image)
                self.stats[llm_source] += 1
                return answers, llm_source

        self.stats['none'] += 1
        return [], 'none'

    def _ask_llm(self, frage: str, laenge: int) -> tuple[list[str], str]:
        """Fragt Claude (bevorzugt) oder Groq."""
        if self.use_claude:
            from kreuzwort.lexikon.claude_fallback import ask_claude
            answers = ask_claude(frage, laenge)
            if answers:
                return answers, 'claude'

        if self.use_groq:
            answers = ask_groq(frage, laenge)
            if answers:
                return answers, 'groq'

        return [], 'none'

    def _save(self, q_key: str, answers: list[str],
              frage_original: str, laenge: int, source_image: int):
        """Speichert Antworten in Cache UND DB."""
        # In-Memory-Cache
        if q_key in self.cache:
            existing = set(self.cache[q_key])
            existing.update(answers)
            self.cache[q_key] = list(existing)
        else:
            self.cache[q_key] = answers

        # SQLite-DB persistieren — Upsert in einem Schritt
        from kreuzwort.lexikon.db import _get_connection
        try:
            conn = _get_connection(self.db_path)
            cursor = conn.cursor()
            answers_str = ",".join(answers)

            # Existiert der Eintrag schon (egal welches source_image)?
            cursor.execute(
                "SELECT id FROM questions WHERE question_text = ?",
                (q_key,)
            )
            row = cursor.fetchone()

            if row:
                # Update: Antworten ergänzen
                cursor.execute(
                    "SELECT possible_answers FROM questions WHERE id = ?",
                    (row[0],)
                )
                existing_answers = cursor.fetchone()[0] or ""
                if existing_answers:
                    all_answers = set(existing_answers.split(","))
                    all_answers.update(answers)
                    answers_str = ",".join(all_answers)

                cursor.execute("""
                    UPDATE questions
                    SET possible_answers = ?, is_missing = 0
                    WHERE id = ?
                """, (answers_str, row[0]))
            else:
                # Insert: Neuer Eintrag mit Antworten
                cursor.execute("""
                    INSERT INTO questions
                    (question_text, question_text_ocr_raw, question_text_ocr_cleaned,
                     answer_length, source_image_num, is_missing, category,
                     possible_answers)
                    VALUES (?, ?, ?, ?, ?, 0, 'crossword', ?)
                """, (q_key, frage_original, q_key,
                      laenge, source_image, answers_str))

            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_stats(self) -> dict:
        """Gibt Statistiken über die Suche zurück."""
        return dict(self.stats)
