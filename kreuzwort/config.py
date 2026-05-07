"""
Zentrale Konfiguration — Pfade und Umgebungserkennung.

Erkennt automatisch ob wir in Ona, Colab oder lokal laufen
und setzt die Datenpfade entsprechend.
"""

import os
from pathlib import Path


def _detect_runtime() -> str:
    """Erkennt die Laufzeitumgebung."""
    # Explizit gesetzt hat Vorrang
    explicit = os.environ.get("RUNTIME_ENV")
    if explicit:
        return explicit.lower()

    # Colab hat immer /content
    if os.path.exists("/content"):
        return "colab"

    # Ona hat /workspaces
    if os.path.exists("/workspaces"):
        return "ona"

    return "local"


RUNTIME = _detect_runtime()

# --- Datenpfade ---
if RUNTIME == "colab":
    DATA_ROOT = Path("/content/drive/MyDrive/Schwedenraetsel_Backup/Kreuzworträtsel_Optimized")
elif RUNTIME == "ona":
    DATA_ROOT = Path("/workspaces/ONA/data")
else:
    DATA_ROOT = Path.home() / "kreuzwort_data"

INPUT_FOLDER = DATA_ROOT / "input_data"
OUTPUT_FOLDER = DATA_ROOT / "scanner_results"
MODELS_FOLDER = DATA_ROOT / "models"
METADATA_FOLDER = DATA_ROOT / "metadata"
SUPERLEXIKON_DB = DATA_ROOT / "superlexikon_db" / "superlexikon.db"

# --- Rätsel-Dimensionen (Standard: Schwedenrätsel) ---
ANZAHL_ZEILEN = 15
ANZAHL_SPALTEN = 12

# --- API Keys ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_Roche")


def _has_build_cli() -> bool:
    """Prüft ob build-cli verfügbar und eingeloggt ist."""
    import subprocess
    try:
        result = subprocess.run(
            ["build-cli", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and len(result.stdout.strip()) > 20
    except Exception:
        return False


# Claude via build-cli verfügbar? (nur auf Laptop)
HAS_CLAUDE = _has_build_cli() if RUNTIME == "local" else False

# --- Ordner anlegen ---
def ensure_folders():
    """Erstellt alle nötigen Ordner falls sie nicht existieren."""
    for folder in [INPUT_FOLDER, OUTPUT_FOLDER, MODELS_FOLDER, METADATA_FOLDER,
                   SUPERLEXIKON_DB.parent]:
        folder.mkdir(parents=True, exist_ok=True)
