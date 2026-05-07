"""
KI-Scanner — CNN-Inference auf Rätsel-PNGs.

Nutzt ein vortrainiertes Keras-Modell um jede Zelle eines
Schwedenrätsels zu klassifizieren (Pfeil, Frage, leer, etc.).

Erzeugt grid_classes.npy — das 2D-Array mit Klassifikationen.
"""

import numpy as np
from pathlib import Path
from PIL import Image

from kreuzwort.config import (
    INPUT_FOLDER, OUTPUT_FOLDER, MODELS_FOLDER,
    ANZAHL_ZEILEN, ANZAHL_SPALTEN, ensure_folders
)

# Keras wird lazy importiert (TensorFlow ist groß)
_model = None
_klassen_namen = None


def _load_model(model_dir: Path = None):
    """Lädt Keras-Modell und Metadaten (einmalig)."""
    global _model, _klassen_namen

    if _model is not None:
        return

    from tensorflow import keras

    model_dir = model_dir or MODELS_FOLDER

    # Modell suchen
    for name in ["CELL5_cnn_model_v2_optimized.keras",
                 "CELL5_cnn_model_v2_optimized.h5",
                 "raetsel_gehirn_kompass.keras"]:
        model_path = model_dir / name
        if model_path.exists():
            _model = keras.models.load_model(str(model_path))
            break

    if _model is None:
        raise FileNotFoundError(f"Kein Keras-Modell gefunden in {model_dir}")

    # Metadaten laden
    meta_path = model_dir / "CELL5_metadata_v2_optimized.npy"
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadaten nicht gefunden: {meta_path}")

    metadata = np.load(str(meta_path), allow_pickle=True).item()
    _klassen_namen = metadata['categories']


def scan_riddle(img_num: str,
                model_dir: Path = None,
                anzahl_zeilen: int = ANZAHL_ZEILEN,
                anzahl_spalten: int = ANZAHL_SPALTEN,
                verbose: bool = True) -> np.ndarray | None:
    """
    Klassifiziert alle Zellen eines Rätsel-PNGs mit dem CNN.

    Args:
        img_num: Rätsel-Nummer als String (z.B. '165')
        model_dir: Pfad zum Modell-Ordner (optional)
        anzahl_zeilen: Anzahl Zeilen im Rätsel
        anzahl_spalten: Anzahl Spalten im Rätsel
        verbose: Fortschrittsausgabe

    Returns:
        2D numpy array mit Klassifikationen, oder None bei Fehler.
        Speichert auch grid_classes_NNN.npy.
    """
    from tensorflow import keras

    ensure_folders()
    _load_model(model_dir)

    # PNG laden
    png_path = INPUT_FOLDER / f"{img_num}.png"
    if not png_path.exists():
        if verbose:
            print(f"  PNG nicht gefunden: {png_path}")
        return None

    img = Image.open(str(png_path)).convert('RGB')
    if verbose:
        print(f"  Bild geladen: {img.width}x{img.height} px")

    dyn_w = img.width / anzahl_spalten
    dyn_h = img.height / anzahl_zeilen

    grid_classes = np.empty((anzahl_zeilen, anzahl_spalten), dtype=object)
    confidences = []

    for r in range(anzahl_zeilen):
        for c in range(anzahl_spalten):
            left = round(c * dyn_w)
            top = round(r * dyn_h)
            right = round((c + 1) * dyn_w)
            bottom = round((r + 1) * dyn_h)
            width = right - left
            height = bottom - top

            if width <= 0 or height <= 0:
                grid_classes[r, c] = "error_invalid_dim"
                continue

            cell_img = img.crop((left, top, left + width, top + height)).resize((83, 83))
            img_array = keras.utils.img_to_array(cell_img) / 255.0
            probs = _model.predict(np.expand_dims(img_array, axis=0), verbose=0)[0]
            predicted_idx = np.argmax(probs)
            grid_classes[r, c] = _klassen_namen[predicted_idx]
            confidences.append(float(probs[predicted_idx]))

    if verbose:
        print(f"  {anzahl_zeilen * anzahl_spalten} Zellen klassifiziert, "
              f"Confidence: {np.mean(confidences):.3f}")

    # Speichern
    output_path = OUTPUT_FOLDER / f"grid_classes_{img_num}.npy"
    np.save(str(output_path), grid_classes)
    if verbose:
        print(f"  Gespeichert: {output_path.name}")

    return grid_classes
