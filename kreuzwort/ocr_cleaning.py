"""
OCR Text-Cleaning — bereinigt Tesseract-Output für Rätsel-Fragen.

Mehrstufige Bereinigung: Bindestriche, Todessymbole (†),
verdoppelte Zeichen, ungültige Zeichen, einzelne Endbuchstaben.
"""

import re


def clean_ocr_text(text: str, debug: bool = False) -> tuple[str, bool]:
    """
    Bereinigt OCR-erkannten Text einer Fragezelle.

    Returns:
        (bereinigter_text, hat_artefakte)
        hat_artefakte ist True wenn der Text leer oder unbrauchbar ist.
    """
    text_original = text

    # Grundreinigung
    text = text.replace('▶', '')
    text = re.sub(r'[\x0c\n\t\r\f]+', ' ', text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    if not text:
        return "[LEER]", True

    # FIX 0: Bindestrich-Normalisierung (VOR lowercase!)
    # Trennstriche entfernen: "- wort" → "wort"
    # Bindestriche behalten: "-Präsident" bleibt
    text = re.sub(r'-\s+(?=[a-zäöü])', '', text)
    text = re.sub(r'\s+-\s+(?=[a-zäöü])', '', text)
    text = re.sub(r'\s+-(?=[A-Z])', '-', text)
    text = re.sub(r'-\s+', '-', text)
    text = re.sub(r'\s+', ' ', text)

    if debug:
        print(f"  [FIX 0 - Hyphens] '{text_original}' → '{text}'")

    # Phase 2: Lowercase (NACH Bindestrich-Logik)
    text = text.lower()

    # FIX 0b: Taktangaben — "44-takt" → "4/4-takt", "34-takt" → "3/4-takt"
    text = re.sub(r'\b(\d)(\d)-takt\b', r'\1/\2-takt', text)

    # FIX 1: Todessymbol — "t 1983" → "† 1983"
    text = re.sub(r'\b(?:t|†)\s+(\d{4})\b', r'† \1', text)
    text = re.sub(r'\btt\s+(\d{4})\b', r'†† \1', text)
    text = re.sub(r'\b(?:t|†)\s+([a-zäöü]{3,})\b', r'† \1', text)
    text = re.sub(r'\btt\s+([a-zäöü]{3,})\b', r'†† \1', text)

    # FIX 2: Verdoppelte Zeichen — "Beeeedrängnis" → "Bedrängnis"
    text = re.sub(r'([a-zäöüß])\1{2,}', r'\1\1', text)

    # Phase 3: Ungültige Zeichen entfernen (/ erlaubt für Taktangaben)
    text = re.sub(r'[^a-zA-ZäöüÄÖÜß\s\-\.,:;/0-9†]+', '', text)
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    if not text:
        return "[LEER]", True

    # Phase 4: Einzelner Endbuchstabe entfernen (OCR-Artefakt)
    words = text.split()
    if len(words) > 1 and len(words[-1]) == 1:
        common_single = {'a', 'i', 'u', 'ö', 'ä', 'ü'}
        if words[-1] not in common_single:
            words = words[:-1]
            text = ' '.join(words)

    if debug:
        print(f"  [FINAL] '{text_original}' → '{text}'")

    return text, False


def clean_ocr_numbers(text: str) -> tuple[str, bool]:
    """
    Bereinigt OCR-erkannten Text einer Nummernzelle.
    Extrahiert nur die erste Ziffer.

    Returns:
        (ziffer, hat_artefakte)
    """
    text = text.strip()
    digits = ''.join(c for c in text if c.isdigit())
    if digits:
        return digits[0], False
    return "[LEER]", True
