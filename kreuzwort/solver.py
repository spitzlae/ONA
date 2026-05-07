"""
BacktrackingCSP Solver — löst Schwedenrätsel mit Constraint Satisfaction.

Verwendet Most-Constrained-Variable Heuristik und Soft-Constraint-Filterung
um die Suchraum-Explosion zu begrenzen.
"""

import re
import copy
from collections import defaultdict
from kreuzwort.config import ANZAHL_ZEILEN, ANZAHL_SPALTEN


class BacktrackingCSPSolver:
    """
    Constraint-Satisfaction Solver für Kreuzworträtsel.

    Erwartet Tasks im Format:
        {
            'frage': str,
            'kandidaten': ['WORT1', 'WORT2', ...],
            'koordinaten': [(row, col), (row, col), ...],
            'laenge': int,
            'richtung': 'H' | 'V',
        }
    """

    def __init__(self, tasks: list[dict],
                 anzahl_zeilen: int = ANZAHL_ZEILEN,
                 anzahl_spalten: int = ANZAHL_SPALTEN,
                 verbose: bool = False):
        self.original_tasks = copy.deepcopy(tasks)
        self.tasks = sorted(tasks, key=lambda x: (len(x['kandidaten']), -x['laenge']))
        self.anzahl_zeilen = anzahl_zeilen
        self.anzahl_spalten = anzahl_spalten
        self.verbose = verbose

        self.grid = [["" for _ in range(anzahl_spalten)] for _ in range(anzahl_zeilen)]
        self.best_grid = [["" for _ in range(anzahl_spalten)] for _ in range(anzahl_zeilen)]
        self.best_placed = 0
        self.iterations = 0
        self.backtrack_count = 0
        self.max_iterations = 1_000_000

        self.pos_to_tasks = self._build_pos_to_tasks()

    def _build_pos_to_tasks(self) -> dict:
        """Mapping: Position → Liste von Task-Indizes die diese Position brauchen."""
        pos_map = defaultdict(list)
        for task_idx, task in enumerate(self.tasks):
            for pos in task['koordinaten']:
                pos_map[pos].append(task_idx)
        return pos_map

    def _soft_constraint_filter(self, task_idx: int,
                                valid_candidates: list[str]) -> list[str]:
        """Filtert Kandidaten nach Kompatibilität mit überlappenden Tasks."""
        if len(valid_candidates) <= 1:
            return valid_candidates

        task = self.tasks[task_idx]

        # Finde überlappende Tasks
        overlapping = set()
        for pos in task['koordinaten']:
            for other_idx in self.pos_to_tasks.get(pos, []):
                if other_idx != task_idx:
                    overlapping.add(other_idx)

        if not overlapping:
            return valid_candidates

        scored = []
        for wort in valid_candidates:
            score = 0
            for other_idx in overlapping:
                other = self.tasks[other_idx]

                # Gemeinsame Positionen finden
                common = []
                for pos in task['koordinaten']:
                    if pos in other['koordinaten']:
                        try:
                            i = task['koordinaten'].index(pos)
                            j = other['koordinaten'].index(pos)
                            common.append((pos, i, j))
                        except ValueError:
                            continue

                if not common:
                    score += 1
                    continue

                # Gibt es einen kompatiblen Kandidaten im anderen Task?
                for other_wort in other['kandidaten']:
                    if len(other_wort) != len(other['koordinaten']):
                        continue
                    try:
                        if all(
                            i < len(wort) and j < len(other_wort)
                            and wort[i] == other_wort[j]
                            for _, i, j in common
                        ):
                            score += 1
                            break
                    except (IndexError, KeyError):
                        continue

            scored.append((score, wort))

        scored.sort(key=lambda x: -x[0])

        # Mindestens 50% behalten
        min_keep = max(1, len(valid_candidates) // 2)
        result = [w for _, w in scored[:max(len(scored), min_keep)]]
        return result if result else valid_candidates

    def _get_valid_candidates(self, task_idx: int) -> list[str]:
        """Gibt Kandidaten zurück die mit dem aktuellen Grid kompatibel sind."""
        if task_idx >= len(self.tasks):
            return []

        task = self.tasks[task_idx]
        valid = []

        for wort in task['kandidaten']:
            if len(wort) != len(task['koordinaten']):
                continue

            ok = True
            for i, (zr, zc) in enumerate(task['koordinaten']):
                if i >= len(wort):
                    ok = False
                    break
                cell = self.grid[zr][zc]
                if cell and cell != wort[i]:
                    ok = False
                    break

            if ok:
                valid.append(wort)

        return self._soft_constraint_filter(task_idx, valid)

    def _most_constrained_next(self, start_idx: int) -> int:
        """Most-Constrained-Variable Heuristik: wählt den Task mit wenigsten Kandidaten."""
        if start_idx >= len(self.tasks):
            return start_idx

        min_candidates = float('inf')
        best_idx = start_idx
        search_range = min(start_idx + 15, len(self.tasks))

        for idx in range(start_idx, search_range):
            try:
                candidates = self._get_valid_candidates(idx)
                if candidates and len(candidates) < min_candidates:
                    min_candidates = len(candidates)
                    best_idx = idx
            except Exception:
                continue

        if best_idx != start_idx and best_idx < len(self.tasks):
            self.tasks[start_idx], self.tasks[best_idx] = \
                self.tasks[best_idx], self.tasks[start_idx]
            self.pos_to_tasks = self._build_pos_to_tasks()

        return start_idx

    def solve(self, task_idx: int = 0, placed: int = 0, depth: int = 0) -> bool:
        """Rekursives Backtracking."""
        if self.iterations >= self.max_iterations:
            return False
        if depth > 5000:
            return False

        if task_idx == 0 and depth == 0:
            self.iterations = 0
            self.best_placed = 0
            self.backtrack_count = 0
            self.grid = [["" for _ in range(self.anzahl_spalten)]
                         for _ in range(self.anzahl_zeilen)]

        self.iterations += 1

        if placed > self.best_placed:
            self.best_placed = placed
            self.best_grid = [row[:] for row in self.grid]
            if self.verbose and placed % 5 == 0:
                print(f"  -> Progress: {placed}/{len(self.tasks)}")

        if task_idx >= len(self.tasks):
            return placed == len(self.tasks)

        try:
            task_idx = self._most_constrained_next(task_idx)
        except Exception:
            pass

        if task_idx >= len(self.tasks):
            return False

        task = self.tasks[task_idx]
        koordinaten = task['koordinaten']
        valid = self._get_valid_candidates(task_idx)

        if not valid:
            return False

        for wort in valid:
            if len(wort) != len(koordinaten):
                continue

            # Alte Werte sichern
            backup = [(zr, zc, self.grid[zr][zc]) for zr, zc in koordinaten]

            try:
                for i, (zr, zc) in enumerate(koordinaten):
                    if i < len(wort):
                        self.grid[zr][zc] = wort[i]

                if self.solve(task_idx + 1, placed + 1, depth + 1):
                    return True

                self.backtrack_count += 1
            finally:
                for zr, zc, old in backup:
                    self.grid[zr][zc] = old

        return False

    def solve_with_restarts(self, max_attempts: int = 3) -> bool:
        """Mehrere Lösungsversuche mit Fortschrittsanzeige."""
        if self.verbose:
            print(f"[Solver] Starte Backtracking ({max_attempts} Versuche, "
                  f"{len(self.tasks)} Tasks)...")

        for attempt in range(max_attempts):
            if attempt > 0 and self.verbose:
                print(f"  Versuch {attempt + 1}/{max_attempts}...")

            try:
                success = self.solve(0, 0, 0)

                if success:
                    if self.verbose:
                        print(f"  Vollständig gelöst!")
                    return True

                threshold = len(self.tasks) * 0.80
                if self.best_placed >= threshold:
                    if self.verbose:
                        print(f"  {self.best_placed}/{len(self.tasks)} erreicht")
                    return True

            except Exception as e:
                if self.verbose:
                    print(f"  Fehler in Versuch {attempt + 1}: {e}")
                continue

        if self.verbose:
            print(f"  Best: {self.best_placed}/{len(self.tasks)}")
        return self.best_placed == len(self.tasks)

    def get_result_grid(self) -> list[list[str]]:
        """Gibt das beste gefundene Grid zurück."""
        return self.best_grid


# --- Hilfsfunktionen für Koordinaten-Parsing ---

def parse_koordinaten(coord_str: str) -> tuple[int | None, int | None]:
    """Parst 'Y:3 X:5' zu (3, 5)."""
    match = re.search(r'Y:(\d+).*X:(\d+)', str(coord_str))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def baue_koordinaten_liste(start_str: str, ende_str: str,
                           richtung: str) -> list[tuple[int, int]]:
    """Baut eine Liste von (row, col) Koordinaten von Start bis Ende."""
    start_y, start_x = parse_koordinaten(start_str)
    ende_y, ende_x = parse_koordinaten(ende_str)
    if any(v is None for v in (start_y, start_x, ende_y, ende_x)):
        return []

    koordinaten = []
    if richtung == 'H':
        step = 1 if ende_x >= start_x else -1
        for c in range(start_x, ende_x + step, step):
            koordinaten.append((start_y, c))
    elif richtung == 'V':
        step = 1 if ende_y >= start_y else -1
        for r in range(start_y, ende_y + step, step):
            koordinaten.append((r, start_x))
    return koordinaten
