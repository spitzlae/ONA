"""
PNG-Downloader — lädt Rätsel-Bilder von raetselzentrale.de.

Nutzt Playwright + Chromium um die Webseite zu rendern und
einen Screenshot zu machen. Croppt auf 997×1247px mit Y-Offset -13px.

Braucht: pip install playwright && playwright install chromium
"""

import asyncio
import hashlib
import numpy as np
from pathlib import Path
from PIL import Image
import io

from kreuzwort.config import INPUT_FOLDER, ensure_folders

# Rätsel-URL Template
_URL_TEMPLATE = "https://raetsel.raetselzentrale.de/r/badische/digiheft/schw-12x15-{num}"

# Crop-Dimensionen (fest für diesen Rätseltyp)
CROP_WIDTH = 997
CROP_HEIGHT = 1247
Y_OFFSET_PX = -13


def _verify_png(file_path: Path) -> tuple[bool, int]:
    """Prüft ob ein PNG vollständig und korrekt ist."""
    if not file_path.exists():
        return False, 0

    size = file_path.stat().st_size
    if size < 50000:
        return False, size

    try:
        img = Image.open(str(file_path))
        w, h = img.size
        img.verify()
        return (w == CROP_WIDTH and h == CROP_HEIGHT), size
    except Exception:
        return False, size


async def _download_single(page, riddle_num: int, verbose: bool = True) -> bool:
    """Lädt ein einzelnes Rätsel herunter."""
    try:
        import cv2
    except ImportError:
        # opencv nicht verfügbar — Fallback ohne Y-Offset
        cv2 = None

    num_str = f"{riddle_num:03d}"
    url = _URL_TEMPLATE.format(num=riddle_num)
    png_path = INPUT_FOLDER / f"{num_str}.png"

    # Bereits vorhanden und gültig?
    is_valid, _ = _verify_png(png_path)
    if is_valid:
        if verbose:
            print(f"  {num_str}: bereits vorhanden, überspringe")
        return True

    try:
        await page.goto(url, wait_until='networkidle', timeout=15000)
        await asyncio.sleep(1.5)

        # Screenshot
        screenshot_bytes = await page.screenshot()
        img = Image.open(io.BytesIO(screenshot_bytes))
        img_width, img_height = img.size

        # Zentriert croppen
        left = max(0, (img_width - CROP_WIDTH) // 2)
        top = max(0, (img_height - CROP_HEIGHT) // 2)
        right = min(img_width, left + CROP_WIDTH)
        bottom = min(img_height, top + CROP_HEIGHT)
        cropped_img = img.crop((left, top, right, bottom))

        # Y-Offset Post-Processing
        if cv2 is not None:
            cropped_cv = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2BGR)
            M = np.float32([[1, 0, 0], [0, 1, Y_OFFSET_PX]])
            shifted_cv = cv2.warpAffine(cropped_cv, M, (CROP_WIDTH, CROP_HEIGHT))
            final_img = Image.fromarray(cv2.cvtColor(shifted_cv, cv2.COLOR_BGR2RGB))
        else:
            final_img = cropped_img

        # Speichern
        final_img.save(str(png_path), "PNG", optimize=False)

        # Verifizieren
        is_valid, file_size = _verify_png(png_path)
        if verbose:
            status = "✅" if is_valid else "⚠️"
            print(f"  {num_str}: {status} ({file_size // 1024} KB)")

        return is_valid

    except Exception as e:
        if verbose:
            print(f"  {num_str}: ❌ {str(e)[:60]}")
        return False


async def download_riddles(riddle_numbers: list[int],
                           verbose: bool = True) -> dict:
    """
    Lädt mehrere Rätsel-PNGs herunter.

    Args:
        riddle_numbers: Liste von Rätsel-Nummern
        verbose: Fortschrittsausgabe

    Returns:
        Dict mit Statistiken
    """
    from playwright.async_api import async_playwright

    ensure_folders()
    stats = {'total': len(riddle_numbers), 'success': 0, 'failed': 0, 'skipped': 0}

    if verbose:
        print(f"[Downloader] Lade {len(riddle_numbers)} Rätsel...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1400}
        )
        page = await context.new_page()

        for num in riddle_numbers:
            num_str = f"{num:03d}"
            png_path = INPUT_FOLDER / f"{num_str}.png"

            # Skip wenn schon vorhanden
            is_valid, _ = _verify_png(png_path)
            if is_valid:
                stats['skipped'] += 1
                if verbose:
                    print(f"  {num_str}: bereits vorhanden")
                continue

            success = await _download_single(page, num, verbose)
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1

            await asyncio.sleep(0.5)  # Rate limiting

        await page.close()
        await context.close()
        await browser.close()

    if verbose:
        print(f"[Downloader] Fertig: {stats['success']} neu, "
              f"{stats['skipped']} übersprungen, {stats['failed']} fehlgeschlagen")

    return stats


def download(riddle_numbers: list[int], verbose: bool = True) -> dict:
    """Synchroner Wrapper für download_riddles."""
    return asyncio.run(download_riddles(riddle_numbers, verbose))
