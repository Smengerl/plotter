#!/usr/bin/env python3
"""
pipeline/tests/run_all_stylizers.py — Smoke-Test aller Stilisierer

Verarbeitet ``testimage.png`` einmal mit jedem registrierten Stilisierer
und speichert das Ergebnis als PNG **und** SVG in ``output/``.

Verwendung
----------
    # aus dem Plotter-Wurzelverzeichnis:
    python pipeline/tests/run_all_stylizers.py

    # oder direkt:
    cd pipeline/tests && python run_all_stylizers.py

    # Maximale Bildgröße begrenzen (Standard: 1024 px):
    python pipeline/tests/run_all_stylizers.py --max-side 512

Ausgabe
-------
    pipeline/tests/output/
        testimage_canny.png / testimage_canny.svg
        testimage_xdog.png  / testimage_xdog.svg
        testimage_adaptive.png / testimage_adaptive.svg
        testimage_hed.png   / testimage_hed.svg       (nur wenn controlnet_aux installiert)
        testimage_dexined.png / testimage_dexined.svg (nur wenn controlnet_aux installiert)
        testimage_lineart.png / testimage_lineart.svg (nur wenn controlnet_aux installiert)
        testimage_informative.png / testimage_informative.svg
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

# ---------------------------------------------------------------------------
# Pfad-Bootstrap: damit Imports funktionieren, egal von wo das Skript
# gestartet wird (aus tests/, aus pipeline/ oder aus dem Projekt-Root).
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent
_PIPELINE_DIR = _TESTS_DIR.parent
_PLOTTER_ROOT = _PIPELINE_DIR.parent
for _p in (_PLOTTER_ROOT, _PIPELINE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline.stylizers import STYLE_CHOICES, get_stylizer  # noqa: E402
from pipeline.vectorise import vectorise, paths_to_svg       # noqa: E402
from pipeline.gcode_gen import generate_gcode                 # noqa: E402

# ---------------------------------------------------------------------------
# Konfiguration der Standardparameter je Stilisierer
# ---------------------------------------------------------------------------

#: Konstruktor-Kwargs pro Stil (entspricht vernünftigen Standardwerten)
_STYLE_KWARGS: dict[str, dict] = {
    "canny":       {"low": 50,  "high": 150, "blur": 3},
    "xdog":        {},
    "adaptive":    {"block_size": 11, "c": 4.0, "method": "gaussian", "blur": 0},
    "hed":         {"device": "auto"},
    "dexined":     {"device": "auto"},
    "lineart":     {"device": "auto", "coarse": False, "detect_resolution": 512, "image_resolution": 512},
    "informative": {"device": "auto", "style": 1},
}

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def _print_header() -> None:
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  Stilisierer Smoke-Test{RESET}")
    print(f"{'─' * 60}")


def _run_stylizer(
    name: str,
    image_path: Path,
    output_dir: Path,
    max_side: int,
) -> tuple[bool, str]:
    """
    Führt einen einzelnen Stilisierer aus und speichert PNG + SVG.

    Returns
    -------
    (success, message)
    """
    kwargs = _STYLE_KWARGS.get(name, {})
    png_path = output_dir / f"testimage_{name}.png"
    svg_path = output_dir / f"testimage_{name}.svg"
    gcode_path = output_dir / f"testimage_{name}.gcode"

    try:
        stylizer = get_stylizer(name, **kwargs)
        t0 = time.monotonic()
        binary = stylizer.stylise(image_path, max_side=max_side)
        elapsed_style = time.monotonic() - t0

        # PNG speichern
        cv2.imwrite(str(png_path), binary)

        # SVG: vektorisieren und exportieren
        paths = vectorise(binary)
        paths_to_svg(paths, binary.shape[:2], svg_path)

        # GCode: aus den Pfaden generieren und speichern (sinnvolle Defaults)
        gcode_lines = generate_gcode(paths, binary.shape[:2])
        gcode_text = "\n".join(gcode_lines) + "\n"
        gcode_path.write_text(gcode_text, encoding="utf-8")

        elapsed = time.monotonic() - t0
        return True, (
            f"{elapsed_style:.2f}s  →  {png_path.name}  +  {svg_path.name}"
            f"  ({len(paths)} Pfade)"
        )

    except ImportError as exc:
        # Fehlende optionale Abhängigkeit — überspringen, nicht als Fehler werten
        short = str(exc).split("\n")[0]
        return None, f"übersprungen (fehlende Abhängigkeit: {short})"  # type: ignore[return-value]

    except Exception as exc:  # noqa: BLE001
        return False, f"FEHLER: {exc}"


# ---------------------------------------------------------------------------
# Hauptprogramm
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verarbeitet testimage.png mit allen Stilisierern."
    )
    parser.add_argument(
        "--max-side",
        type=int,
        default=1024,
        metavar="PX",
        help="Maximale Länge der längsten Seite (Standard: 1024)",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=_TESTS_DIR / "testimage.png",
        metavar="PATH",
        help="Eingabebild (Standard: pipeline/tests/testimage.png)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_TESTS_DIR / "output",
        metavar="DIR",
        help="Ausgabeverzeichnis (Standard: pipeline/tests/output/)",
    )
    args = parser.parse_args()

    image_path: Path = args.image.resolve()
    output_dir: Path = args.output_dir.resolve()

    if not image_path.exists():
        print(f"{RED}Fehler: Eingabebild nicht gefunden: {image_path}{RESET}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    _print_header()
    print(f"  Bild      : {image_path}")
    print(f"  Ausgabe   : {output_dir}")
    print(f"  max_side  : {args.max_side} px")
    print(f"  Formate   : PNG + SVG + GCODE")
    print(f"  Stilisierer: {', '.join(STYLE_CHOICES)}")
    print(f"{'─' * 60}\n")

    results: list[tuple[str, bool | None, str]] = []

    for name in STYLE_CHOICES:
        print(f"  [{name:<14}]  … ", end="", flush=True)
        success, msg = _run_stylizer(name, image_path, output_dir, args.max_side)

        if success is True:
            symbol = f"{GREEN}✓{RESET}"
        elif success is None:
            symbol = f"{YELLOW}~{RESET}"
        else:
            symbol = f"{RED}✗{RESET}"

        print(f"{symbol}  {msg}")
        results.append((name, success, msg))

    # Zusammenfassung
    n_ok   = sum(1 for _, s, _ in results if s is True)
    n_skip = sum(1 for _, s, _ in results if s is None)
    n_err  = sum(1 for _, s, _ in results if s is False)

    print(f"\n{'─' * 60}")
    print(
        f"  Ergebnis: {GREEN}{n_ok} erfolgreich{RESET}  "
        f"{YELLOW}{n_skip} übersprungen{RESET}  "
        f"{RED}{n_err} Fehler{RESET}"
    )
    print(f"{'─' * 60}\n")

    if n_ok > 0:
        print(f"  Gespeicherte Dateien in: {output_dir}\n")

    sys.exit(1 if n_err > 0 else 0)


if __name__ == "__main__":
    main()
