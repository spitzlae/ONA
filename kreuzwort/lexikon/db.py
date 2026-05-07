"""
SuperLexikon SQLite-Datenbank.

Speichert Fragen, OCR-Rohdaten, Antworten und deren Quellen.
Wächst mit jedem gelösten Rätsel — je mehr Rätsel, desto besser.
"""

import sqlite3
from pathlib import Path
from kreuzwort.config import SUPERLEXIKON_DB


def _get_connection(db_path: Path = None) -> sqlite3.Connection:
    """Erstellt eine DB-Verbindung mit WAL-Modus für bessere Concurrency."""
    path = db_path or SUPERLEXIKON_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = None) -> bool:
    """Erstellt die DB-Tabelle falls sie nicht existiert."""
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='questions'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_text TEXT UNIQUE NOT NULL,
                    question_text_ocr_raw TEXT,
                    question_text_ocr_cleaned TEXT,
                    answer_length INTEGER,
                    possible_answers TEXT,
                    source_image_num INTEGER,
                    is_missing INTEGER DEFAULT 1,
                    category TEXT DEFAULT 'crossword',
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_question_text ON questions(question_text)")
            cursor.execute("CREATE INDEX idx_source_image ON questions(source_image_num)")
            cursor.execute("CREATE INDEX idx_is_missing ON questions(is_missing)")
            conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"DB init error: {e}")
        return False


def add_question(question_cleaned: str, question_raw: str,
                 answer_length: int, source_image: int,
                 db_path: Path = None) -> str:
    """
    Fügt eine Frage hinzu oder aktualisiert sie.

    Returns: 'added', 'updated', 'duplicate', oder 'error'
    """
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM questions WHERE question_text = ? AND source_image_num = ?",
            (question_cleaned, source_image)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE questions
                SET question_text_ocr_raw = ?,
                    question_text_ocr_cleaned = ?,
                    answer_length = ?,
                    is_missing = 1
                WHERE id = ?
            """, (question_raw, question_cleaned, answer_length, existing[0]))
            conn.commit()
            conn.close()
            return 'updated'
        else:
            try:
                cursor.execute("""
                    INSERT INTO questions
                    (question_text, question_text_ocr_raw, question_text_ocr_cleaned,
                     answer_length, source_image_num, is_missing, category)
                    VALUES (?, ?, ?, ?, ?, 1, 'crossword')
                """, (question_cleaned, question_raw, question_cleaned,
                      answer_length, source_image))
                conn.commit()
                conn.close()
                return 'added'
            except sqlite3.IntegrityError:
                conn.close()
                return 'duplicate'
    except Exception as e:
        return 'error'


def update_answers(question_id: int, solutions: list[str],
                   db_path: Path = None) -> bool:
    """Speichert gefundene Antworten für eine Frage und markiert sie als gelöst."""
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        answers_str = ",".join(solutions) if solutions else ""
        cursor.execute("""
            UPDATE questions
            SET possible_answers = ?, is_missing = 0
            WHERE id = ?
        """, (answers_str, question_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def load_cache(db_path: Path = None) -> dict[str, list[str]]:
    """
    Lädt alle beantworteten Fragen in den Speicher.

    Returns: {frage_lowercase: [ANTWORT1, ANTWORT2, ...]}
    """
    cache = {}
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question_text, possible_answers
            FROM questions
            WHERE possible_answers IS NOT NULL AND possible_answers != ''
        """)
        for question_text, answers in cursor.fetchall():
            q_key = question_text.lower().strip()
            answers_list = [a.strip() for a in answers.split(',') if a.strip()]
            cache[q_key] = answers_list
        conn.close()
    except Exception:
        pass
    return cache


def get_missing_questions(db_path: Path = None) -> list[tuple[int, str, int, int]]:
    """
    Gibt alle unbeantworteten Fragen zurück.

    Returns: [(id, frage, länge, rätsel_nummer), ...]
    """
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, question_text, answer_length, source_image_num
            FROM questions
            WHERE is_missing = 1
            ORDER BY source_image_num, id
        """)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception:
        return []


def delete_riddle_questions(source_image: int, db_path: Path = None) -> int:
    """Löscht alle Fragen eines bestimmten Rätsels. Gibt Anzahl gelöschter Einträge zurück."""
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE source_image_num = ?", (source_image,))
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    except Exception:
        return 0


def get_stats(db_path: Path = None) -> dict:
    """Gibt DB-Statistiken zurück."""
    try:
        conn = _get_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questions")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM questions WHERE is_missing = 0")
        answered = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM questions WHERE is_missing = 1")
        missing = cursor.fetchone()[0]
        conn.close()
        return {'total': total, 'answered': answered, 'missing': missing}
    except Exception:
        return {'total': 0, 'answered': 0, 'missing': 0}
