"""
OCR-Extraktion — liest Fragetexte aus dem Rätsel-PNG.

Nutzt Tesseract OCR auf den vom CNN als 'question' klassifizierten Zellen.
Erzeugt die Datenstrukturen die der Grid-Parser für MCTS-Extraktion braucht.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from kreuzwort.config import ANZAHL_ZEILEN, ANZAHL_SPALTEN
from kreuzwort.grid_parser import is_cell_question, get_cell_bounds
from kreuzwort.ocr_cleaning import clean_ocr_text, clean_ocr_numbers

# Tesseract wird lazy importiert
_tesseract_config = r"-l deu --psm 6"


def _ocr_image(img: Image.Image, config: str = None) -> str:
    """Führt Tesseract OCR auf einem PIL-Image aus."""
    import pytesseract
    config = config or _tesseract_config
    try:
        return pytesseract.image_to_string(img, config=config)
    except Exception:
        return ""


def _preprocess_cell(img: Image.Image, border_trim: int = 0,
                     scale: int = 3) -> Image.Image:
    """Vergrößert und kontrastiert eine Zelle für bessere OCR."""
    if border_trim > 0:
        draw = ImageDraw.Draw(img)
        d = border_trim
        draw.rectangle([0, 0, img.width, d], fill="white")
        draw.rectangle([0, img.height - d, img.width, img.height], fill="white")
        draw.rectangle([0, 0, d, img.height], fill="white")
        draw.rectangle([img.width - d, 0, img.width, img.height], fill="white")

    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    return img.convert('L')


def extract_ocr(png_path: str,
                grid_classes: np.ndarray,
                anzahl_zeilen: int = ANZAHL_ZEILEN,
                anzahl_spalten: int = ANZAHL_SPALTEN,
                verbose: bool = True) -> tuple[dict, dict]:
    """
    Führt OCR auf allen Frage-Zellen aus.

    Args:
        png_path: Pfad zum Rätsel-PNG
        grid_classes: 2D array mit CNN-Klassifikationen
        anzahl_zeilen: Raster-Zeilen
        anzahl_spalten: Raster-Spalten
        verbose: Fortschrittsausgabe

    Returns:
        (ocr_results_by_question_cell, question_splits)
        - ocr_results: {(row, col): "frage_text"} für einfache Fragen
        - question_splits: {(row, col): ["frage1", "frage2"]} für Multi-Fragen
    """
    img = Image.open(png_path).convert('RGB')

    dyn_w = img.width / anzahl_spalten
    # Wie im Original: 8px vom unteren Rand abziehen
    reduced_height = max(0, img.height - 8)
    dyn_h = reduced_height / anzahl_zeilen

    ocr_results = {}
    question_splits = {}
    total_cells = 0
    artifact_count = 0

    for r in range(anzahl_zeilen):
        for c in range(anzahl_spalten):
            predicted_class = str(grid_classes[r, c])

            if not (is_cell_question(predicted_class) or 'number_only' in predicted_class):
                continue

            total_cells += 1
            left, top, right, bottom = get_cell_bounds(
                r, c, dyn_h, dyn_w, img.width, img.height
            )
            w = right - left
            h = bottom - top
            cell_img = img.crop((left, top, left + w, top + h))

            is_multiple = 'question_multiple' in predicted_class.lower()

            if is_multiple:
                # Multi-Frage-Zelle: obere und untere Hälfte separat OCR-en
                mid_y = 44  # Feste Teilung wie im Original
                upper = cell_img.crop((0, 0, w, mid_y))
                lower = cell_img.crop((0, mid_y, w, 89))

                upper_processed = _preprocess_cell(upper.copy())
                lower_processed = _preprocess_cell(lower.copy())

                upper_raw = _ocr_image(upper_processed)
                lower_raw = _ocr_image(lower_processed)

                upper_text, upper_bad = clean_ocr_text(upper_raw)
                lower_text, lower_bad = clean_ocr_text(lower_raw)

                parts = []
                if not upper_bad and upper_text not in ['[LEER]', '[ERROR]']:
                    parts.append(upper_text)
                if not lower_bad and lower_text not in ['[LEER]', '[ERROR]']:
                    parts.append(lower_text)

                if len(parts) == 2:
                    question_splits[(r, c)] = parts
                elif len(parts) == 1:
                    ocr_results[(r, c)] = parts[0]
                else:
                    artifact_count += 1

            else:
                # Einfache Zelle: mehrere Border-Trims versuchen
                best_text = "[LEER]"
                best_artifact = True

                for trim in [0, 5, 10, 15]:
                    processed = _preprocess_cell(cell_img.copy(), border_trim=trim)
                    raw = _ocr_image(processed)

                    if 'number_only' in predicted_class:
                        text, artifact = clean_ocr_numbers(raw)
                    else:
                        text, artifact = clean_ocr_text(raw)

                    if not artifact:
                        best_text = text
                        best_artifact = False
                        break

                if best_artifact:
                    artifact_count += 1
                elif best_text not in ['[LEER]', '[ERROR]']:
                    # Pipe-Zeichen = Multi-Frage die OCR als eine Zelle erkannt hat
                    if '|' in best_text:
                        parts = [p.strip() for p in best_text.split('|')]
                        question_splits[(r, c)] = parts
                    else:
                        ocr_results[(r, c)] = best_text

    if verbose:
        print(f"  OCR: {total_cells} Zellen, "
              f"{len(ocr_results)} einfach, "
              f"{len(question_splits)} multi, "
              f"{artifact_count} Artefakte")

    return ocr_results, question_splits
