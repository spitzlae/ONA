"""
PNG-Downloader — lädt Rätsel-Bilder von raetselzentrale.de.

Strategie:
1. Playwright nativ (wenn installiert)
2. Docker-Fallback (Playwright im Container)

Croppt auf 997×1247px mit Y-Offset -13px.
"""

import asyncio
import subprocess
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

# Docker Image für Playwright
_DOCKER_IMAGE = "mcr.microsoft.com/playwright/python:v1.52.0-noble"


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


def _has_playwright() -> bool:
    """Prüft ob Playwright nativ verfügbar ist UND Chromium installiert ist."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False

    # Prüfe ob der Browser tatsächlich existiert
    cache_dir = Path.home() / ".cache" / "ms-playwright"
    if not cache_dir.exists():
        return False

    # Suche nach einer chromium-Binary
    for p in cache_dir.rglob("chrome-headless-shell"):
        if p.is_file():
            return True
    for p in cache_dir.rglob("chromium"):
        if p.is_file():
            return True

    return False


def _has_docker() -> bool:
    """Prüft ob Docker verfügbar und lauffähig ist."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# --- Inline-Script das im Docker-Container läuft ---
_DOCKER_DOWNLOAD_SCRIPT = '''
import asyncio, sys, io, json
import numpy as np
from PIL import Image
from playwright.async_api import async_playwright

URL_TEMPLATE = "https://raetsel.raetselzentrale.de/r/badische/digiheft/schw-12x15-{num}"
CROP_WIDTH = 997
CROP_HEIGHT = 1247
Y_OFFSET_PX = -13

async def download(numbers, output_dir):
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(viewport={"width": 1920, "height": 1400})
        page = await context.new_page()

        for num in numbers:
            num_str = f"{num:03d}"
            png_path = f"{output_dir}/{num_str}.png"
            url = URL_TEMPLATE.format(num=num)

            try:
                await page.goto(url, wait_until="networkidle", timeout=15000)
                await asyncio.sleep(1.5)

                screenshot_bytes = await page.screenshot()
                img = Image.open(io.BytesIO(screenshot_bytes))
                img_width, img_height = img.size

                left = max(0, (img_width - CROP_WIDTH) // 2)
                top = max(0, (img_height - CROP_HEIGHT) // 2)
                right = min(img_width, left + CROP_WIDTH)
                bottom = min(img_height, top + CROP_HEIGHT)
                cropped = img.crop((left, top, right, bottom))

                try:
                    import cv2
                    cropped_cv = cv2.cvtColor(np.array(cropped), cv2.COLOR_RGB2BGR)
                    M = np.float32([[1, 0, 0], [0, 1, Y_OFFSET_PX]])
                    shifted = cv2.warpAffine(cropped_cv, M, (CROP_WIDTH, CROP_HEIGHT))
                    final = Image.fromarray(cv2.cvtColor(shifted, cv2.COLOR_BGR2RGB))
                except ImportError:
                    final = cropped

                final.save(png_path, "PNG", optimize=False)
                results[num_str] = True
                print(f"  {num_str}: ok", flush=True)
            except Exception as e:
                results[num_str] = False
                print(f"  {num_str}: FEHLER {str(e)[:60]}", flush=True)

            await asyncio.sleep(0.5)

        await browser.close()

    print(json.dumps(results), flush=True)

numbers = [int(x) for x in sys.argv[1].split(",")]
output_dir = sys.argv[2]
asyncio.run(download(numbers, output_dir))
'''


def _download_via_docker(riddle_numbers: list[int], verbose: bool = True) -> dict:
    """Lädt Rätsel-PNGs via Docker-Container mit Playwright."""
    ensure_folders()
    stats = {'total': len(riddle_numbers), 'success': 0, 'failed': 0, 'skipped': 0}

    # Bereits vorhandene überspringen
    to_download = []
    for num in riddle_numbers:
        png_path = INPUT_FOLDER / f"{num:03d}.png"
        is_valid, _ = _verify_png(png_path)
        if is_valid:
            stats['skipped'] += 1
            if verbose:
                print(f"  {num:03d}: bereits vorhanden")
        else:
            to_download.append(num)

    if not to_download:
        if verbose:
            print("[Downloader/Docker] Alle PNGs bereits vorhanden.")
        return stats

    numbers_csv = ",".join(str(n) for n in to_download)
    input_dir = str(INPUT_FOLDER.resolve())

    if verbose:
        print(f"[Downloader/Docker] Lade {len(to_download)} Rätsel via Container...")

    # Script als temporäre Datei schreiben und in den Container mounten
    import tempfile
    script_file = Path(tempfile.mktemp(suffix=".py", prefix="pw_download_"))
    script_file.write_text(_DOCKER_DOWNLOAD_SCRIPT)

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{input_dir}:/output",
        "-v", f"{script_file}:/tmp/download.py:ro",
        _DOCKER_IMAGE,
        "bash", "-c",
        f"pip install -q Pillow numpy playwright==1.52.0 && python3 /tmp/download.py {numbers_csv} /output"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            if verbose:
                print(f"[Downloader/Docker] Container-Fehler (exit {result.returncode})")
                if result.stderr:
                    print(f"  {result.stderr[:200]}")
            stats['failed'] = len(to_download)
            return stats

    except subprocess.TimeoutExpired:
        if verbose:
            print("[Downloader/Docker] Timeout (120s)")
        stats['failed'] = len(to_download)
        return stats
    finally:
        script_file.unlink(missing_ok=True)

    # Ergebnisse verifizieren
    for num in to_download:
        png_path = INPUT_FOLDER / f"{num:03d}.png"
        is_valid, file_size = _verify_png(png_path)
        if is_valid:
            stats['success'] += 1
        else:
            stats['failed'] += 1
            if verbose:
                print(f"  {num:03d}: Verifikation fehlgeschlagen")

    if verbose:
        print(f"[Downloader/Docker] Fertig: {stats['success']} neu, "
              f"{stats['skipped']} übersprungen, {stats['failed']} fehlgeschlagen")

    return stats


async def _download_native(riddle_numbers: list[int], verbose: bool = True) -> dict:
    """Lädt Rätsel-PNGs via nativem Playwright."""
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

            is_valid, _ = _verify_png(png_path)
            if is_valid:
                stats['skipped'] += 1
                if verbose:
                    print(f"  {num_str}: bereits vorhanden")
                continue

            try:
                try:
                    import cv2
                except ImportError:
                    cv2 = None

                url = _URL_TEMPLATE.format(num=num)
                await page.goto(url, wait_until='networkidle', timeout=15000)
                await asyncio.sleep(1.5)

                screenshot_bytes = await page.screenshot()
                img = Image.open(io.BytesIO(screenshot_bytes))
                img_width, img_height = img.size

                left = max(0, (img_width - CROP_WIDTH) // 2)
                top = max(0, (img_height - CROP_HEIGHT) // 2)
                right = min(img_width, left + CROP_WIDTH)
                bottom = min(img_height, top + CROP_HEIGHT)
                cropped_img = img.crop((left, top, right, bottom))

                if cv2 is not None:
                    cropped_cv = cv2.cvtColor(np.array(cropped_img), cv2.COLOR_RGB2BGR)
                    M = np.float32([[1, 0, 0], [0, 1, Y_OFFSET_PX]])
                    shifted_cv = cv2.warpAffine(cropped_cv, M, (CROP_WIDTH, CROP_HEIGHT))
                    final_img = Image.fromarray(cv2.cvtColor(shifted_cv, cv2.COLOR_BGR2RGB))
                else:
                    final_img = cropped_img

                final_img.save(str(png_path), "PNG", optimize=False)

                is_valid, file_size = _verify_png(png_path)
                if is_valid:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

                if verbose:
                    status = "ok" if is_valid else "FEHLER"
                    print(f"  {num_str}: {status} ({file_size // 1024} KB)")

            except Exception as e:
                stats['failed'] += 1
                if verbose:
                    print(f"  {num_str}: FEHLER {str(e)[:60]}")

            await asyncio.sleep(0.5)

        await browser.close()

    if verbose:
        print(f"[Downloader] Fertig: {stats['success']} neu, "
              f"{stats['skipped']} übersprungen, {stats['failed']} fehlgeschlagen")

    return stats


def download(riddle_numbers: list[int], verbose: bool = True) -> dict:
    """
    Synchroner Einstiegspunkt — wählt automatisch die beste Methode.

    Priorität: Playwright nativ > Docker > Fehler
    """
    if _has_playwright():
        if verbose:
            print("[Downloader] Nutze Playwright (nativ)")
        return asyncio.run(_download_native(riddle_numbers, verbose))

    if _has_docker():
        if verbose:
            print("[Downloader] Playwright nicht verfügbar, nutze Docker-Fallback")
        return _download_via_docker(riddle_numbers, verbose)

    if verbose:
        print("[Downloader] FEHLER: Weder Playwright noch Docker verfügbar.")
        print("  Installiere: pip install playwright && playwright install chromium")
        print("  Oder:        sudo apt install docker.io")
    return {'total': len(riddle_numbers), 'success': 0,
            'failed': len(riddle_numbers), 'skipped': 0}
