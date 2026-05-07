"""
Grid-Parser — Arrow-Decoding und Rätsel-Navigation.

Versteht die CNN-Klassifikationen (arrow_DOWN_DOWN_no_number etc.)
und berechnet daraus Schreibrichtungen, Fragetexte und Lösungslängen.
"""

import numpy as np
from kreuzwort.config import ANZAHL_ZEILEN, ANZAHL_SPALTEN


# Mapping: CNN-Klasse → Schreibrichtung + Position der Fragezelle relativ zum Pfeil
ARROW_DECODE = {
    # Einfache Pfeile
    'arrow_DOWN_DOWN_no_number':      {'write_direction': (1, 0), 'question_relative_pos_to_arrow': (-1, 0)},
    'arrow_DOWN_DOWN_with_number':    {'write_direction': (1, 0), 'question_relative_pos_to_arrow': (-1, 0)},
    'arrow_RIGHT_RIGHT_no_number':    {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (0, -1)},
    'arrow_RIGHT_RIGHT_with_number':  {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (0, -1)},
    'arrow_DOWN_RIGHT_no_number':     {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (-1, 0)},
    'arrow_DOWN_RIGHT_with_number':   {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (-1, 0)},
    'arrow_UP_RIGHT_no_number':       {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (1, 0)},
    'arrow_UP_RIGHT_with_number':     {'write_direction': (0, 1), 'question_relative_pos_to_arrow': (1, 0)},
    'arrow_LEFT_DOWN_no_number':      {'write_direction': (1, 0), 'question_relative_pos_to_arrow': (0, 1)},
    'arrow_LEFT_DOWN_with_number':    {'write_direction': (1, 0), 'question_relative_pos_to_arrow': (0, 1)},

    # Combo-Pfeile (eine Zelle, zwei Richtungen)
    'arrow_combo_RIGHT_DOWN_no_number': {
        'arrows': [
            {'direction': (0, 1), 'question_relative_pos_to_arrow': (0, -1)},
            {'direction': (1, 0), 'question_relative_pos_to_arrow': (-1, 0)},
        ]
    },
    'arrow_combo_RIGHT_DOWN_with_number': {
        'arrows': [
            {'direction': (0, 1), 'question_relative_pos_to_arrow': (0, -1)},
            {'direction': (1, 0), 'question_relative_pos_to_arrow': (-1, 0)},
        ]
    },
}


def decode_arrow(arrow_type: str) -> dict | None:
    """Gibt die Arrow-Info zurück oder None wenn unbekannt."""
    return ARROW_DECODE.get(arrow_type, None)


def is_cell_arrow(cell) -> bool:
    """Prüft ob eine Zelle ein Pfeil ist."""
    return str(cell).strip().startswith('arrow') if cell else False


def is_cell_question(cell) -> bool:
    """Prüft ob eine Zelle eine Frage enthält."""
    return 'question' in str(cell).strip().lower() if cell else False


def get_solution_length(grid: np.ndarray, start_row: int, start_col: int,
                        direction: tuple, anzahl_zeilen: int = ANZAHL_ZEILEN,
                        anzahl_spalten: int = ANZAHL_SPALTEN) -> int:
    """Zählt leere Zellen ab start_pos in Richtung direction bis eine Frage/Rand kommt."""
    if not (0 <= start_row < anzahl_zeilen and 0 <= start_col < anzahl_spalten):
        return 0
    length = 0
    row, col = start_row, start_col
    while 0 <= row < anzahl_zeilen and 0 <= col < anzahl_spalten:
        cell = grid[row, col]
        if is_cell_question(cell):
            break
        length += 1
        row += direction[0]
        col += direction[1]
    return length


def get_cell_bounds(r: int, c: int, dyn_h: float, dyn_w: float,
                    img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Berechnet Pixel-Koordinaten (left, top, right, bottom) einer Rasterzelle."""
    left = int(round(c * dyn_w))
    top = int(round(r * dyn_h))
    right = int(round((c + 1) * dyn_w))
    bottom = int(round((r + 1) * dyn_h))
    left = max(0, min(left, img_w - 1))
    top = max(0, min(top, img_h - 1))
    right = max(left + 1, min(right, img_w))
    bottom = max(top + 1, min(bottom, img_h))
    return left, top, right, bottom


def extract_mcts_entries(grid_classes: np.ndarray,
                         question_splits: dict,
                         ocr_results_by_question_cell: dict,
                         anzahl_zeilen: int = ANZAHL_ZEILEN,
                         anzahl_spalten: int = ANZAHL_SPALTEN) -> list[dict]:
    """
    Extrahiert alle Aufgaben (Frage + Richtung + Start/Ende + Länge) aus dem Grid.

    Args:
        grid_classes: 2D numpy array mit CNN-Klassifikationen pro Zelle
        question_splits: {(row, col): [frage1, frage2]} für Multi-Frage-Zellen
        ocr_results_by_question_cell: {(row, col): "frage_text"} für einfache Zellen

    Returns:
        Liste von Dicts mit Frage, Richtung, Start, Ende, Länge
    """
    mcts_entries = []

    # Phase 1: Multi-Frage-Zellen identifizieren (Zellen auf die mehrere Pfeile zeigen)
    multi_question_cells = {}
    for r_arrow in range(anzahl_zeilen):
        for c_arrow in range(anzahl_spalten):
            arrow_cell = str(grid_classes[r_arrow, c_arrow])
            if not is_cell_arrow(arrow_cell):
                continue
            arrow_info = decode_arrow(arrow_cell)
            if arrow_info is None:
                continue

            if 'write_direction' in arrow_info:
                q_rel = arrow_info['question_relative_pos_to_arrow']
                q_r, q_c = r_arrow + q_rel[0], c_arrow + q_rel[1]
                if 0 <= q_r < anzahl_zeilen and 0 <= q_c < anzahl_spalten:
                    multi_question_cells.setdefault((q_r, q_c), []).append({
                        'arrow_pos': (r_arrow, c_arrow),
                        'direction': 'V' if arrow_info['write_direction'][0] != 0 else 'H',
                        'type': 'single',
                    })

            if 'arrows' in arrow_info:
                for idx, sub_arrow in enumerate(arrow_info['arrows']):
                    q_rel = sub_arrow['question_relative_pos_to_arrow']
                    q_r, q_c = r_arrow + q_rel[0], c_arrow + q_rel[1]
                    if 0 <= q_r < anzahl_zeilen and 0 <= q_c < anzahl_spalten:
                        multi_question_cells.setdefault((q_r, q_c), []).append({
                            'arrow_pos': (r_arrow, c_arrow),
                            'combo_idx': idx,
                            'direction': 'V' if sub_arrow['direction'][0] != 0 else 'H',
                            'type': 'combo',
                        })

    # Phase 2: MCTS-Einträge aus Pfeilen generieren
    for r_arrow in range(anzahl_zeilen):
        for c_arrow in range(anzahl_spalten):
            arrow_cell = str(grid_classes[r_arrow, c_arrow])
            if not is_cell_arrow(arrow_cell):
                continue
            arrow_info = decode_arrow(arrow_cell)
            if arrow_info is None:
                continue

            # Combo-Pfeile (zwei Richtungen aus einer Zelle)
            if 'arrows' in arrow_info:
                for idx, sub in enumerate(arrow_info['arrows']):
                    _add_entry(mcts_entries, grid_classes, r_arrow, c_arrow,
                               sub['direction'], sub['question_relative_pos_to_arrow'],
                               question_splits, ocr_results_by_question_cell,
                               multi_question_cells, anzahl_zeilen, anzahl_spalten,
                               arrow_cell, combo_idx=idx)

            # Einfache Pfeile
            elif 'write_direction' in arrow_info:
                _add_entry(mcts_entries, grid_classes, r_arrow, c_arrow,
                           arrow_info['write_direction'],
                           arrow_info['question_relative_pos_to_arrow'],
                           question_splits, ocr_results_by_question_cell,
                           multi_question_cells, anzahl_zeilen, anzahl_spalten,
                           arrow_cell)

    return mcts_entries


def _add_entry(entries, grid, r_arrow, c_arrow, direction_vec, q_rel,
               question_splits, ocr_results, multi_cells,
               n_rows, n_cols, arrow_type, combo_idx=None):
    """Hilfsfunktion: erstellt einen MCTS-Eintrag wenn Frage und Länge gültig sind."""
    q_r, q_c = r_arrow + q_rel[0], c_arrow + q_rel[1]
    if not (0 <= q_r < n_rows and 0 <= q_c < n_cols):
        return

    sol_length = get_solution_length(grid, r_arrow, c_arrow, direction_vec, n_rows, n_cols)
    if sol_length <= 0:
        return

    sol_end_r = r_arrow + (sol_length - 1) * direction_vec[0]
    sol_end_c = c_arrow + (sol_length - 1) * direction_vec[1]
    sol_dir = 'V' if direction_vec[0] != 0 else 'H'

    # Fragetext bestimmen
    question_text = _resolve_question(
        q_r, q_c, r_arrow, c_arrow,
        question_splits, ocr_results, multi_cells, combo_idx
    )

    if question_text and question_text not in ['[LEER]', '[ERROR]']:
        entries.append({
            'Frage': question_text,
            'Richtung': sol_dir,
            'Start': f'Y:{r_arrow} X:{c_arrow}',
            'Ende': f'Y:{sol_end_r} X:{sol_end_c}',
            'Länge': sol_length,
            'Pfeil_Zelle_Y': r_arrow,
            'Pfeil_Zelle_X': c_arrow,
            'Pfeiltyp': arrow_type,
        })


def _resolve_question(q_r, q_c, r_arrow, c_arrow,
                      question_splits, ocr_results, multi_cells, combo_idx):
    """Bestimmt den Fragetext — berücksichtigt Multi-Frage-Zellen und Combo-Pfeile."""
    if (q_r, q_c) in question_splits:
        parts = question_splits[(q_r, q_c)]
        if combo_idx is not None:
            # Combo-Pfeil: Index direkt verwenden
            return parts[combo_idx] if combo_idx < len(parts) else ""
        # Einfacher Pfeil auf Multi-Frage-Zelle
        arrow_count = len(multi_cells.get((q_r, q_c), []))
        if arrow_count >= 2 and len(parts) >= 2:
            if r_arrow < q_r or c_arrow < q_c:
                return parts[0]
            else:
                return parts[1]
        return parts[0] if parts else ""

    if (q_r, q_c) in ocr_results:
        return ocr_results[(q_r, q_c)]

    return ""


def parse_image_input(user_input: str) -> list[int]:
    """Parst Eingabe wie '165', '1,2,3', '1-5,10' zu einer sortierten Liste von Nummern."""
    numbers = set()
    if not user_input:
        return []
    parts = [p.strip() for p in user_input.split(',') if p.strip()]
    for part in parts:
        if '-' in part and part.count('-') == 1:
            try:
                a, b = part.split('-')
                start, end = int(a.strip()), int(b.strip())
                if start <= end:
                    numbers.update(range(start, end + 1))
                else:
                    numbers.update(range(end, start + 1))
            except ValueError:
                pass
        else:
            try:
                numbers.add(int(part))
            except ValueError:
                pass
    return sorted(numbers)
