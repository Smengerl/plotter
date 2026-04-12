"""
pipeline/tests/test_gcode_gen.py — Unit-Tests für die GCode-Generierung

Läuft ohne Hardware (kein Plotter, kein GRBL).
Kein cv2 oder Modell nötig — nur numpy.

Aufruf:
    cd plotter/pipeline
    pytest tests/
"""

import numpy as np
import pytest

import sys
from pathlib import Path

# Sicherstellen, dass 'pipeline/' im Suchpfad liegt
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pipeline.gcode_gen import generate_gcode
from pipeline.grbl_sender import _filter_gcode


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _simple_paths() -> list:
    """Zwei einfache L-förmige Pfade in Pixelkoordinaten."""
    path1 = np.array([[0, 0], [100, 0], [100, 100]], dtype=np.float32)
    path2 = np.array([[10, 10], [50, 90]], dtype=np.float32)
    return [path1, path2]


def _parse_coord(token: str) -> float:
    """'X12.345' → 12.345"""
    return float(token[1:])


def _extract_moves(lines: list[str]) -> list[tuple[float, float]]:
    """Extrahiert (X, Y) aus allen G1-Zeilen."""
    moves = []
    for line in lines:
        clean = line.split(";")[0].strip()
        if not clean.startswith("G1"):
            continue
        parts = clean.split()
        coords = {p[0]: float(p[1:]) for p in parts[1:] if p[0] in "XY"}
        if "X" in coords and "Y" in coords:
            moves.append((coords["X"], coords["Y"]))
    return moves


# ---------------------------------------------------------------------------
# Tests: GCode-Generierung
# ---------------------------------------------------------------------------

class TestGenerateGcode:

    def test_returns_list_of_strings(self):
        paths = _simple_paths()
        lines = generate_gcode(paths, image_shape=(200, 200))
        assert isinstance(lines, list)
        assert all(isinstance(l, str) for l in lines)

    def test_contains_initialisation_commands(self):
        lines = generate_gcode(_simple_paths(), image_shape=(200, 200))
        joined = "\n".join(lines)
        assert "G21" in joined       # Maßeinheit mm
        assert "G90" in joined       # Absolute Koordinaten

    def test_pen_down_and_up_commands_present(self):
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(100, 100),
            pen_down_cmd="M3 S1000",
            pen_up_cmd="M5",
        )
        joined = "\n".join(lines)
        assert "M3 S1000" in joined
        assert "M5" in joined

    def test_custom_pen_commands(self):
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(100, 100),
            pen_down_cmd="M3 S500",
            pen_up_cmd="M5",
        )
        joined = "\n".join(lines)
        assert "M3 S500" in joined

    def test_coordinates_within_target_bounds(self):
        """Alle Koordinaten müssen innerhalb des definierten Zeichenbereichs liegen."""
        w, h = 150.0, 200.0
        ox, oy = 10.0, 10.0
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(300, 400),
            target_width_mm=w,
            target_height_mm=h,
            origin_x=ox,
            origin_y=oy,
            keep_aspect=True,
        )
        moves = _extract_moves(lines)
        assert len(moves) > 0
        for x, y in moves:
            assert ox - 0.01 <= x <= ox + w + 0.01, f"X={x} außerhalb [{ox}, {ox+w}]"
            assert oy - 0.01 <= y <= oy + h + 0.01, f"Y={y} außerhalb [{oy}, {oy+h}]"

    def test_aspect_ratio_preserved(self):
        """Bei keep_aspect=True darf nur eine Achse die volle Länge nutzen."""
        img_w, img_h = 200, 100  # 2:1 Bild
        target_w, target_h = 100.0, 100.0  # quadratisches Ziel
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(img_h, img_w),
            target_width_mm=target_w,
            target_height_mm=target_h,
            origin_x=0.0,
            origin_y=0.0,
            keep_aspect=True,
        )
        moves = _extract_moves(lines)
        max_x = max(x for x, y in moves)
        max_y = max(y for x, y in moves)
        # Bild 2:1 → X nutzt 100mm voll, Y maximal 50mm
        assert max_x <= target_w + 0.01
        assert max_y <= target_h / 2.0 + 0.01

    def test_no_aspect_ratio(self):
        """Bei keep_aspect=False können beide Achsen voll genutzt werden."""
        lines = generate_gcode(
            [np.array([[0, 0], [200, 100]], dtype=np.float32)],
            image_shape=(100, 200),
            target_width_mm=100.0,
            target_height_mm=100.0,
            origin_x=0.0,
            origin_y=0.0,
            keep_aspect=False,
        )
        moves = _extract_moves(lines)
        max_x = max(x for x, y in moves)
        max_y = max(y for x, y in moves)
        assert max_x == pytest.approx(100.0, abs=0.01)
        assert max_y == pytest.approx(100.0, abs=0.01)

    def test_feedrate_in_gcode(self):
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(100, 100),
            feedrate_draw=1200,
            feedrate_travel=2800,
        )
        joined = "\n".join(lines)
        assert "F1200" in joined
        assert "F2800" in joined

    def test_pen_delay_present(self):
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(100, 100),
            pen_delay_ms=150,
        )
        joined = "\n".join(lines)
        assert "G4 P150" in joined

    def test_no_pen_delay_when_zero(self):
        lines = generate_gcode(
            _simple_paths(),
            image_shape=(100, 100),
            pen_delay_ms=0,
        )
        joined = "\n".join(lines)
        assert "G4" not in joined

    def test_y_axis_flip(self):
        """
        Ein Punkt am oberen Bildrand (py=0) muss die höchste Y-Koordinate haben.
        Ein Punkt am unteren Bildrand (py=img_h) muss die kleinste Y-Koordinate haben.
        """
        img_h = 100
        path_top    = np.array([[50,  0 ]], dtype=np.float32)  # oben im Bild
        path_bottom = np.array([[50, 100]], dtype=np.float32)  # unten im Bild

        lines_top = generate_gcode(
            [np.array([[50, 0], [50, 1]], dtype=np.float32)],
            image_shape=(img_h, 100),
            origin_x=0.0, origin_y=0.0,
            target_width_mm=100.0, target_height_mm=100.0,
        )
        lines_bottom = generate_gcode(
            [np.array([[50, 99], [50, 100]], dtype=np.float32)],
            image_shape=(img_h, 100),
            origin_x=0.0, origin_y=0.0,
            target_width_mm=100.0, target_height_mm=100.0,
        )
        y_top    = max(y for _, y in _extract_moves(lines_top))
        y_bottom = min(y for _, y in _extract_moves(lines_bottom))
        assert y_top > y_bottom

    def test_empty_paths_returns_valid_gcode(self):
        lines = generate_gcode([], image_shape=(100, 100))
        assert len(lines) > 0
        joined = "\n".join(lines)
        assert "G21" in joined

    def test_single_point_path_skipped(self):
        single = [np.array([[50, 50]], dtype=np.float32)]
        lines = generate_gcode(single, image_shape=(100, 100))
        # Kein Pfad mit nur 1 Punkt → kein M3-Befehl
        joined = "\n".join(lines)
        # Initialisierungs-M5 ist da, aber kein M3
        assert "M3" not in joined


# ---------------------------------------------------------------------------
# Tests: GCode-Filter
# ---------------------------------------------------------------------------

class TestFilterGcode:

    def test_removes_empty_lines(self):
        lines = ["G1 X10 Y10", "", "  ", "G1 X20 Y20"]
        result = list(_filter_gcode(lines))
        assert result == ["G1 X10 Y10", "G1 X20 Y20"]

    def test_removes_full_comment_lines(self):
        lines = ["; dies ist ein Kommentar", "G1 X10 Y10"]
        result = list(_filter_gcode(lines))
        assert result == ["G1 X10 Y10"]

    def test_strips_inline_comments(self):
        lines = ["G1 X10 Y10  ; inline Kommentar"]
        result = list(_filter_gcode(lines))
        assert result == ["G1 X10 Y10"]

    def test_preserves_pen_commands(self):
        lines = ["M3 S1000", "M5"]
        result = list(_filter_gcode(lines))
        assert result == ["M3 S1000", "M5"]
