"""
Kreuzworträtsel Pipeline — vom Download bis zur Lösung.

Vollständiger Ablauf:
    0. Downloader: PNG von raetselzentrale.de (wenn Playwright vorhanden)
    1. CNN-Scanner: PNG → grid_classes.npy
    2. OCR: Fragetexte aus dem Bild lesen
    3. MCTS-Extraktion: Aufgaben aus Grid + OCR ableiten
    4. Lexikon-Lookup: Antworten suchen (DB → Crawler → Claude/Groq)
    5. Backtracking-Solver: Rätsel lösen
    6. Renderer: Bitmap + Text-Report

Verwendung:
    python -m kreuzwort.main 165
    python -m kreuzwort.main 1-5,10
    python -m kreuzwort.main --download 165    # Download erzwingen

Erkennt automatisch was verfügbar ist:
    - Playwright oder Docker installiert → Downloader aktiv
    - Keras-Modell vorhanden → Scanner aktiv
    - Tesseract installiert → OCR aktiv
    - build-cli eingeloggt → Claude Sonnet als LLM
    - Sonst → Groq Llama als LLM
"""

import sys
import csv
import time
import numpy as np
from pathlib import Path

from kreuzwort.config import (
    INPUT_FOLDER, OUTPUT_FOLDER, MODELS_FOLDER,
    ANZAHL_ZEILEN, ANZAHL_SPALTEN, ensure_folders
)
from kreuzwort.grid_parser import (
    extract_mcts_entries, parse_image_input
)
from kreuzwort.text_cleaner import text_cleaner
from kreuzwort.lexikon.db import init_db
from kreuzwort.lexikon.lookup import LexikonLookup
from kreuzwort.solver import BacktrackingCSPSolver, baue_koordinaten_liste
from kreuzwort.renderer import render_solution, render_text_report


def _has_download() -> bool:
    """Prüft ob Download möglich ist (Playwright nativ oder Docker)."""
    from kreuzwort.downloader import _has_playwright, _has_docker
    return _has_playwright() or _has_docker()


def _has_keras_model() -> bool:
    """Prüft ob ein Keras-Modell vorhanden ist."""
    for name in ["CELL5_cnn_model_v2_optimized.keras",
                 "CELL5_cnn_model_v2_optimized.h5",
                 "raetsel_gehirn_kompass.keras"]:
        if (MODELS_FOLDER / name).exists():
            return True
    return False


def _has_tesseract() -> bool:
    """Prüft ob Tesseract installiert ist."""
    import subprocess
    try:
        result = subprocess.run(['tesseract', '--version'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _load_grid_from_file(img_num: str) -> np.ndarray | None:
    """Lädt vorberechnete grid_classes.npy."""
    for name in [f"grid_classes_{img_num}.npy", f"grid_classes_{int(img_num)}.npy"]:
        path = OUTPUT_FOLDER / name
        if path.exists():
            return np.load(str(path), allow_pickle=True)
    return None


def _load_mcts_csv(img_num: str) -> list[dict] | None:
    """Lädt vorberechnete MCTS-Koordinaten aus CSV."""
    for name in [f"{img_num}_mcts_coords.csv", f"{int(img_num)}_mcts_coords.csv"]:
        path = OUTPUT_FOLDER / name
        if path.exists():
            entries = []
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append(row)
            return entries
    return None


def _save_mcts_csv(img_num: str, entries: list[dict]):
    """Speichert MCTS-Einträge als CSV für spätere Wiederverwendung."""
    if not entries:
        return
    path = OUTPUT_FOLDER / f"{img_num}_mcts_coords.csv"
    fieldnames = ['Frage', 'Richtung', 'Start', 'Ende', 'Länge',
                  'Pfeil_Zelle_Y', 'Pfeil_Zelle_X', 'Pfeiltyp']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({k: entry.get(k, '') for k in fieldnames})


def process_riddle(img_num: str, lookup: LexikonLookup,
                   use_scanner: bool = False, use_ocr: bool = False,
                   verbose: bool = True) -> dict:
    """
    Verarbeitet ein einzelnes Rätsel.

    Drei Modi:
    1. Scanner + OCR: Alles selbst machen (Keras + Tesseract nötig)
    2. Grid + OCR: grid_classes.npy laden, OCR selbst (Tesseract nötig)
    3. Fallback: grid_classes.npy + mcts_coords.csv laden (Colab-Vorarbeit)
    """
    result = {'img_num': img_num, 'success': False, 'tasks': 0, 'solved': 0}

    if verbose:
        print(f"\n{'='*60}")
        print(f"RÄTSEL {img_num}")
        print(f"{'='*60}")

    png_path = INPUT_FOLDER / f"{img_num}.png"

    # --- Phase 1: Grid bekommen ---
    grid_classes = None

    if use_scanner:
        if verbose:
            print("  [Phase 1] CNN-Scanner...")
        from kreuzwort.scanner import scan_riddle
        grid_classes = scan_riddle(img_num, verbose=verbose)
    else:
        grid_classes = _load_grid_from_file(img_num)
        if grid_classes is not None and verbose:
            print(f"  Grid geladen: {grid_classes.shape}")

    if grid_classes is None:
        if verbose:
            print("  Kein Grid verfügbar — überspringe")
        return result

    anzahl_zeilen, anzahl_spalten = grid_classes.shape

    # --- Phase 2: MCTS-Einträge bekommen ---
    mcts_entries = None

    if use_ocr and png_path.exists():
        if verbose:
            print("  [Phase 2] OCR-Extraktion...")
        from kreuzwort.ocr_extract import extract_ocr
        ocr_results, question_splits = extract_ocr(
            str(png_path), grid_classes, anzahl_zeilen, anzahl_spalten, verbose
        )

        if verbose:
            print("  [Phase 3] MCTS-Extraktion...")
        mcts_entries = extract_mcts_entries(
            grid_classes, question_splits, ocr_results,
            anzahl_zeilen, anzahl_spalten
        )
        if verbose:
            print(f"  {len(mcts_entries)} MCTS-Einträge extrahiert")

        # CSV speichern für spätere Wiederverwendung
        _save_mcts_csv(img_num, mcts_entries)
    else:
        # Fallback: vorberechnete CSV laden
        mcts_csv = _load_mcts_csv(img_num)
        if mcts_csv:
            mcts_entries = mcts_csv
            if verbose:
                print(f"  MCTS CSV geladen: {len(mcts_entries)} Einträge")
        else:
            if verbose:
                print("  Keine MCTS-Daten — überspringe")
            return result

    # --- Phase 4: Antworten suchen + Tasks bauen ---
    if verbose:
        print("  [Phase 4] Lexikon-Lookup...")

    tasks = []
    for entry in mcts_entries:
        frage = str(entry.get('Frage', '')).strip()
        richtung = entry.get('Richtung', '')
        laenge = int(entry.get('Länge', 0))
        start_str = str(entry.get('Start', ''))
        ende_str = str(entry.get('Ende', ''))

        koordinaten = baue_koordinaten_liste(start_str, ende_str, richtung)
        if not koordinaten or len(koordinaten) != laenge:
            continue

        frage_clean = text_cleaner(frage).lower()
        fragen_liste = [f.strip() for f in frage_clean.split('|') if f.strip()]

        alle_kandidaten = []
        for f in fragen_liste:
            answers, source = lookup.get_answers(f, laenge)
            alle_kandidaten.extend(answers)

        alle_kandidaten = list(dict.fromkeys(alle_kandidaten))

        if alle_kandidaten:
            tasks.append({
                'frage': frage_clean,
                'frage_original': frage,
                'richtung': richtung,
                'koordinaten': koordinaten,
                'laenge': laenge,
                'kandidaten': alle_kandidaten,
                'loesung': None,
            })

    result['tasks'] = len(tasks)
    if verbose:
        print(f"  Tasks mit Kandidaten: {len(tasks)}/{len(mcts_entries)}")
        stats = lookup.get_stats()
        print(f"  Quellen: DB={stats['db']} Crawler={stats['crawler']} "
              f"Groq={stats['groq']} None={stats['none']}")

    if not tasks:
        if verbose:
            print("  Keine Tasks — überspringe")
        return result

    # --- Phase 5: Solver ---
    if verbose:
        print(f"\n  [Phase 5] Solver...")
    start_time = time.time()
    solver = BacktrackingCSPSolver(
        tasks, anzahl_zeilen, anzahl_spalten, verbose=verbose
    )
    success = solver.solve_with_restarts(max_attempts=3)
    duration = time.time() - start_time

    for task in tasks:
        wort = ""
        for zr, zc in task['koordinaten']:
            wort += solver.best_grid[zr][zc] if solver.best_grid[zr][zc] else "?"
        task['loesung'] = wort

    geloest = sum(1 for t in tasks if t['loesung'] and '?' not in t['loesung'])
    result['solved'] = geloest
    result['success'] = success

    solver_stats = {
        'duration': duration,
        'iterations': solver.iterations,
        'backtrack_count': solver.backtrack_count,
    }

    if verbose:
        print(f"  Gelöst: {geloest}/{len(tasks)} "
              f"({100*geloest/len(tasks):.0f}%) in {duration:.2f}s")

    # --- Phase 6: Output ---
    if png_path.exists():
        bitmap_path = render_solution(png_path, tasks, grid_classes)
        if verbose:
            print(f"  Bitmap: {bitmap_path.name}")

    report_path = render_text_report(tasks, img_num, solver_stats)
    if verbose:
        print(f"  Report: {report_path.name}")

    return result


def main(args: list[str] = None):
    """Haupteinstiegspunkt."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Verwendung: python -m kreuzwort.main [--download] <bildnummer(n)>")
        print("Beispiele:  python -m kreuzwort.main 165")
        print("            python -m kreuzwort.main 1-5,10")
        print("            python -m kreuzwort.main --download 165")
        sys.exit(1)

    # --download Flag parsen
    force_download = "--download" in args
    args = [a for a in args if a != "--download"]

    user_input = ' '.join(args)
    img_numbers = parse_image_input(user_input)
    if not img_numbers:
        print(f"Keine gültigen Bildnummern in '{user_input}'")
        sys.exit(1)

    # Setup
    ensure_folders()
    init_db()

    # Fähigkeiten erkennen
    from kreuzwort.config import HAS_CLAUDE
    has_download = _has_download()
    has_model = _has_keras_model()
    has_tess = _has_tesseract()

    if has_model and has_tess:
        mode = "Vollständig (Scanner + OCR + Solver)"
        use_scanner = True
        use_ocr = True
    elif has_tess:
        mode = "OCR + Solver (Grid aus Datei)"
        use_scanner = False
        use_ocr = True
    else:
        mode = "Fallback (CSV + Solver)"
        use_scanner = False
        use_ocr = False

    print(f"Modus: {mode}")
    print(f"  Download: {'vorhanden' if has_download else 'nicht gefunden'}")
    print(f"  Keras-Modell: {'vorhanden' if has_model else 'nicht gefunden'}")
    print(f"  Tesseract: {'vorhanden' if has_tess else 'nicht gefunden'}")
    print(f"  LLM: {'Claude Sonnet (build-cli)' if HAS_CLAUDE else 'Groq Llama'}")

    # Download wenn nötig
    if force_download or (has_download and any(
        not (INPUT_FOLDER / f"{n:03d}.png").exists() for n in img_numbers
    )):
        missing = [n for n in img_numbers
                   if not (INPUT_FOLDER / f"{n:03d}.png").exists()]
        if missing:
            print(f"\n[Phase 0] Download {len(missing)} fehlende PNGs...")
            from kreuzwort.downloader import download
            download(missing, verbose=True)

    lookup = LexikonLookup()
    print(f"  SuperLexikon: {len(lookup.cache)} Einträge im Cache")
    print(f"\nVerarbeite {len(img_numbers)} Rätsel: {img_numbers}")

    results = []
    for num in img_numbers:
        img_num = str(num).zfill(3)
        result = process_riddle(
            img_num, lookup,
            use_scanner=use_scanner, use_ocr=use_ocr,
            verbose=True
        )
        results.append(result)

    # Zusammenfassung
    print(f"\n{'='*60}")
    print("ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    total_tasks = sum(r['tasks'] for r in results)
    total_solved = sum(r['solved'] for r in results)
    for r in results:
        if r['tasks'] > 0:
            pct = 100 * r['solved'] / r['tasks']
            print(f"  Rätsel {r['img_num']}: {r['solved']}/{r['tasks']} ({pct:.0f}%)")
        else:
            print(f"  Rätsel {r['img_num']}: übersprungen")

    if total_tasks > 0:
        print(f"\n  Gesamt: {total_solved}/{total_tasks} "
              f"({100*total_solved/total_tasks:.0f}%)")

    lookup_stats = lookup.get_stats()
    print(f"  Lexikon-Quellen: {lookup_stats}")


if __name__ == '__main__':
    main()
