"""
Text-Cleaning für Rätsel-Fragen.

Entfernt typografische Artefakte, Klammern, Zeilenumbrüche
und Lösungszahlen aus OCR-erkanntem Text.
"""

import re


def text_cleaner(frage: str) -> str:
    """Bereinigt eine Rätsel-Frage von OCR-Artefakten und Formatierung."""
    sauber = frage.replace("\u201a", "")   # ‚
    sauber = sauber.replace("\u2018", "")  # '
    sauber = sauber.replace("\u2019", "")  # '
    sauber = sauber.replace("\n", " ").replace("<br>", "")

    # Klammern entfernen: (ugs.), (Mz.), (Abk.) etc.
    sauber = re.sub(r"\(.*?\)", "", sauber)

    # Lösungszahlen entfernen: [1], [2] etc.
    sauber = re.sub(r"\[\d+\]", "", sauber)

    return sauber.strip()
