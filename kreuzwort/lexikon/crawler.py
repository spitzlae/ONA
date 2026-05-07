"""
Web-Crawler für Kreuzworträtsel-Lösungen.

Versucht zwei Quellen:
  1. kreuzwort-raetsel.net (primär)
  2. wort-suchen.de (fallback)

Beide blockieren Cloud-IPs — funktioniert nur von Colab oder Laptop.
"""

import urllib.parse
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
_TIMEOUT = 10
_BLACKLIST = {"START", "SYNONYME", "FACEBOOK", "TWITTER", "YOUTUBE", "GENDERN",
              "SUCHE", "HOME", "KONTAKT", "IMPRESSUM", "DATENSCHUTZ",
              "WORTSUCHE", "ANAGRAMME", "SUDOKU", "STARTSEITE", "NEWS",
              "LOGIN", "FORMULAR", "MASTERMIND", "SONSTIGE"}


def _crawl_kreuzwort_raetsel(frage: str, laenge: int) -> list[str]:
    """Sucht auf kreuzwort-raetsel.net."""
    try:
        q = urllib.parse.quote(frage.strip())
        url = f"https://www.kreuzwort-raetsel.net/suche/?q={q}"
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        answers = []
        for link in soup.find_all("a"):
            wort = link.get_text(strip=True).upper()
            if (wort.isalpha()
                    and len(wort) == laenge
                    and wort not in _BLACKLIST
                    and wort not in answers):
                answers.append(wort)
        return answers
    except Exception:
        return []


def _crawl_wort_suchen(frage: str, laenge: int) -> list[str]:
    """Sucht auf wort-suchen.de (Fallback)."""
    try:
        q = urllib.parse.quote_plus(frage.strip())
        pattern = '_' * laenge
        url = f"https://www.wort-suchen.de/kreuzwortraetsel-hilfe/loesungen/{q}/{pattern}/"
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        answers = []
        for link in soup.find_all("a", href=True):
            wort = link.get_text(strip=True).upper()
            if (wort.isalpha()
                    and len(wort) == laenge
                    and wort not in _BLACKLIST
                    and wort not in answers):
                answers.append(wort)
        return answers
    except Exception:
        return []


def crawl_answers(frage: str, laenge: int) -> list[str]:
    """
    Sucht Kreuzworträtsel-Lösungen im Web.

    Versucht kreuzwort-raetsel.net zuerst, dann wort-suchen.de als Fallback.

    Returns:
        Liste von Antworten in Großbuchstaben, oder leere Liste bei Fehler.
    """
    answers = _crawl_kreuzwort_raetsel(frage, laenge)
    if answers:
        return answers

    return _crawl_wort_suchen(frage, laenge)
