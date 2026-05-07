"""
Bitmap-Renderer — zeichnet gelöste Buchstaben ins Rätsel-Bild.

Rote Buchstaben für Lösungsfelder (mit Nummer), grüne für normale Felder.
"""

import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from kreuzwort.config import OUTPUT_FOLDER


# Fallback-Fonts in Reihenfolge der Präferenz
_FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Lädt einen Font mit Fallback."""
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_solution(png_path: Path | str,
                    tasks: list[dict],
                    grid_classes: np.ndarray,
                    output_path: Path | str = None) -> Path:
    """
    Zeichnet die Lösung ins Original-PNG.

    Args:
        png_path: Pfad zum Original-Rätsel-PNG
        tasks: Liste von Tasks mit 'loesung' und 'koordinaten'
        grid_classes: CNN-Klassifikationen (für rote Felder)
        output_path: Ausgabepfad (optional, wird automatisch generiert)

    Returns:
        Pfad zur gespeicherten Bitmap
    """
    png_path = Path(png_path)
    img = Image.open(png_path).convert('RGB')
    draw = ImageDraw.Draw(img)

    anzahl_zeilen, anzahl_spalten = grid_classes.shape
    dyn_w = img.width / anzahl_spalten
    dyn_h = img.height / anzahl_zeilen

    font_size = max(10, int(dyn_h * 0.5))
    font = _load_font(font_size)

    # Rote Felder erkennen (Zellen mit Nummer = Lösungsbuchstaben)
    red_fields = set()
    for r in range(anzahl_zeilen):
        for c in range(anzahl_spalten):
            cell = str(grid_classes[r, c]).lower()
            if '_with_number' in cell or 'number_only' in cell:
                red_fields.add((r, c))

    drawn = 0
    for task in tasks:
        loesung = task.get('loesung', '')
        if not loesung or '?' in loesung:
            continue

        for i, buchstabe in enumerate(loesung):
            if i >= len(task['koordinaten']):
                break
            zr, zc = task['koordinaten'][i]

            zx = int(zc * dyn_w)
            zy = int(zr * dyn_h)

            farbe = "red" if (zr, zc) in red_fields else "green"

            # Buchstabe zentrieren
            bbox = draw.textbbox((0, 0), buchstabe, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = zx + (dyn_w - tw) / 2
            ty = zy + (dyn_h - th) / 2

            draw.text((tx, ty), buchstabe, fill=farbe, font=font)
            drawn += 1

    # Speichern
    if output_path is None:
        stem = png_path.stem
        output_path = OUTPUT_FOLDER / f"{stem}_Geloest.png"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path))

    return output_path


def render_text_report(tasks: list[dict],
                       img_num: str,
                       solver_stats: dict,
                       output_path: Path | str = None) -> Path:
    """
    Erstellt einen Text-Bericht der Lösung.

    Args:
        tasks: Liste von Tasks mit 'loesung'
        img_num: Rätsel-Nummer
        solver_stats: Dict mit iterations, backtrack_count, duration
        output_path: Ausgabepfad (optional)

    Returns:
        Pfad zum gespeicherten Bericht
    """
    if output_path is None:
        output_path = OUTPUT_FOLDER / f"{img_num}_Geloest_Text.txt"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geloest = sum(1 for t in tasks if t.get('loesung') and '?' not in t['loesung'])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"KREUZWORTRÄTSEL LÖSUNG - BILD {img_num}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Gelöst: {geloest}/{len(tasks)}\n")
        f.write(f"Laufzeit: {solver_stats.get('duration', 0):.4f}s\n")
        f.write(f"Iterationen: {solver_stats.get('iterations', 0)}\n")
        f.write(f"Backtracks: {solver_stats.get('backtrack_count', 0)}\n\n")
        f.write("LÖSUNGEN:\n")
        f.write("-" * 80 + "\n")
        for task in tasks:
            loesung = task.get('loesung', '???')
            status = "✅" if loesung and "?" not in loesung else "⚠️"
            frage = task.get('frage', '?')
            f.write(f"{status} {frage:<50} = {loesung}\n")

    return output_path
