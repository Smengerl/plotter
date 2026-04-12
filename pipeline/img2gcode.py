#!/usr/bin/env python3
"""
img2gcode — Image-to-GCode Pipeline für den G-code Pen Plotter

Pipeline-Schritte:
  1. Stylisation  — Bild → vereinfachter Linienstil (Canny, XDoG oder NN-Modell)
  2. Vektorisierung — Binärbild → SVG-Pfade (potrace / skimage-Konturen)
  3. GCode-Generierung — Pfade → GRBL-GCode mit Pen-Up/Down
  4. Senden (optional) — GCode seriell an GRBL-Controller

Aufruf-Beispiele:
  python img2gcode.py photo.jpg
  python img2gcode.py photo.jpg --width 180 --height 250
  python img2gcode.py photo.jpg --style xdog --sigma 0.5 --threshold 30
  python img2gcode.py photo.jpg --style hed --model-path models/hed.pth
  python img2gcode.py photo.jpg --send --port /dev/tty.usbmodem* --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

# Sicherstellen, dass das plotter/-Verzeichnis im Suchpfad liegt,
# egal ob das Skript direkt oder als Modul aufgerufen wird.
_plotter_root = _Path(__file__).parent.parent
if str(_plotter_root) not in _sys.path:
    _sys.path.insert(0, str(_plotter_root))

from pipeline.stylise import stylise_image, STYLE_CHOICES
from pipeline.vectorise import vectorise, paths_to_svg
from pipeline.gcode_gen import generate_gcode
from pipeline.grbl_sender import send_gcode

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="img2gcode",
        description="Konvertiert ein Bild in GRBL-GCode für den Pen Plotter.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # --- Eingabe / Ausgabe ---
    p.add_argument("image", type=Path, help="Pfad zum Eingabebild")
    p.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Ausgabe-GCode-Datei (Standard: <bild>.gcode)",
    )

    # --- Zielgröße ---
    size = p.add_argument_group("Zielgröße (Plotter-Koordinaten in mm)")
    size.add_argument(
        "--width",
        type=float,
        default=180.0,
        help="Zeichenbreite in mm (X-Achse)",
    )
    size.add_argument(
        "--height",
        type=float,
        default=250.0,
        help="Zeichenhöhe in mm (Y-Achse)",
    )
    size.add_argument(
        "--origin-x",
        type=float,
        default=5.0,
        help="X-Ursprung (linker Rand) in mm",
    )
    size.add_argument(
        "--origin-y",
        type=float,
        default=5.0,
        help="Y-Ursprung (unterer Rand) in mm",
    )
    size.add_argument(
        "--keep-aspect",
        action="store_true",
        default=True,
        help="Seitenverhältnis beibehalten (passt in --width × --height)",
    )

    # --- Stil-Modul ---
    style = p.add_argument_group("Stil-Umwandlung")
    style.add_argument(
        "--style",
        choices=STYLE_CHOICES,
        default="canny",
        help=(
            "Methode zur Linien-Extraktion:\n"
            "  canny    — klassischer Canny-Kantendetektor (schnell, kein Modell)\n"
            "  xdog     — eXtended Difference-of-Gaussians (Sketch-Look)\n"
            "  adaptive — Adaptiver Schwellenwert (gut für Fotos/Skizzen, kein Modell)\n"
            "  hed      — Holistically-nested Edge Detection (neuronales Netz)\n"
            "  dexined  — DexiNed neuronales Kantenmodell"
        ),
    )

    # Canny
    canny = p.add_argument_group("Canny-Parameter (--style canny)")
    canny.add_argument("--canny-low",  type=int, default=50,  help="Untere Schwelle")
    canny.add_argument("--canny-high", type=int, default=150, help="Obere Schwelle")
    canny.add_argument("--canny-blur", type=int, default=3,   help="Gauss-Blur Kernelgröße (ungerade)")

    # XDoG
    xdog = p.add_argument_group("XDoG-Parameter (--style xdog)")
    xdog.add_argument("--sigma",     type=float, default=0.4,  help="σ der kleinen Gauss-Funktion")
    xdog.add_argument("--k-sigma",   type=float, default=1.6,  help="Verhältnis σ_groß / σ_klein")
    xdog.add_argument("--epsilon",   type=float, default=0.0,  help="Schwellenwert (-1..1, 0 = Median)")
    xdog.add_argument("--phi",       type=float, default=10.0, help="Stärke der weichen Schwelle")
    xdog.add_argument("--threshold", type=float, default=20.0, help="Finale Binarisierungsschwelle (0–255)")

    # Neuronale Modelle (HED / DexiNed / Lineart / Informative Drawings)
    nn = p.add_argument_group("Modell-Parameter (--style hed / dexined / lineart / informative)")
    nn.add_argument(
        "--model-path",
        type=Path,
        default=None,
        help="Pfad zur Modelldatei (.pth / .onnx) oder zum Modell-Verzeichnis. "
             "Wird automatisch heruntergeladen wenn None.",
    )
    nn.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps"],
        default="auto",
        help="PyTorch-Gerät für Inferenz. "
             "\"auto\" (Standard) wählt automatisch cuda > mps > cpu.",
    )
    nn.add_argument(
        "--inform-style",
        type=int,
        choices=[1, 2],
        default=1,
        dest="inform_style",
        help="Modell-Variante für --style informative: "
             "1 = schärfere Linien (model.pth), "
             "2 = weichere Linien (model2.pth). Standard: 1.",
    )
    nn.add_argument(
        "--lineart-coarse",
        action="store_true",
        default=False,
        dest="lineart_coarse",
        help="Für --style lineart: grobe Linien verwenden (sk_model2.pth). "
             "Standard: feine Linien (sk_model.pth).",
    )
    nn.add_argument(
        "--lineart-detect-res",
        type=int,
        default=512,
        dest="lineart_detect_res",
        metavar="PX",
        help="Für --style lineart: interne Modell-Auflösung in Pixeln. "
             "Höher = mehr Details, langsamer. Standard: 512.",
    )
    nn.add_argument(
        "--lineart-image-res",
        type=int,
        default=512,
        dest="lineart_image_res",
        metavar="PX",
        help="Für --style lineart: Ausgabeauflösung des Detektors. "
             "Standard: 512.",
    )

    # Adaptive Threshold
    adap = p.add_argument_group("Adaptive-Threshold-Parameter (--style adaptive)")
    adap.add_argument(
        "--block-size",
        type=int,
        default=11,
        help="Größe der lokalen Nachbarschaft in Pixeln (ungerade, ≥ 3). "
             "Kleinere Werte → feinere Details.",
    )
    adap.add_argument(
        "--adapt-c",
        type=float,
        default=2.0,
        help="Konstante, die vom lokalen Schwellenwert subtrahiert wird. "
             "Höhere Werte unterdrücken Rauschen.",
    )
    adap.add_argument(
        "--adapt-method",
        choices=["gaussian", "mean"],
        default="gaussian",
        help="Berechnungsmethode: gaussian (glatter) oder mean",
    )
    adap.add_argument(
        "--adapt-blur",
        type=int,
        default=0,
        help="Gauss-Blur-Kernelgröße vor der Schwellenwert-Berechnung (0 = aus)",
    )

    # Gemeinsam: Ausgabegröße für Stil-Schritt
    style.add_argument(
        "--style-res",
        type=int,
        default=1024,
        help="Längste Seite des Zwischenbildes (px) vor Stil-Umwandlung",
    )

    # --- Vektorisierung ---
    vec = p.add_argument_group("Vektorisierung")
    vec.add_argument(
        "--min-path-px",
        type=int,
        default=10,
        help="Minimale Pfadlänge in Pixeln (kürzere Pfade werden verworfen)",
    )
    vec.add_argument(
        "--simplify-eps",
        type=float,
        default=1.5,
        help="Ramer-Douglas-Peucker Toleranz (px) für Pfadvereinfachung",
    )

    # --- GCode-Parameter ---
    gcode = p.add_argument_group("GCode-Parameter")
    gcode.add_argument("--feedrate-draw",  type=int, default=1500, help="Vorschub Zeichnen (mm/min)")
    gcode.add_argument("--feedrate-travel",type=int, default=3000, help="Vorschub Verfahren (mm/min)")
    gcode.add_argument("--pen-down-cmd",   type=str, default="M3 S1000", help="GRBL-Befehl Stift runter")
    gcode.add_argument("--pen-up-cmd",     type=str, default="M5",       help="GRBL-Befehl Stift hoch")
    gcode.add_argument("--pen-delay-ms",   type=int, default=100,        help="Wartezeit nach Pen-Down (ms)")

    # --- Senden ---
    send = p.add_argument_group("Senden an Plotter")
    send.add_argument(
        "--send",
        action="store_true",
        default=False,
        help="GCode direkt an GRBL senden",
    )
    send.add_argument("--port",    type=str, default="/dev/tty.usbmodem1101", help="Serieller Port")
    send.add_argument("--baud",    type=int, default=115200,                  help="Baudrate")
    send.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="GCode parsen + anzeigen, aber nicht senden",
    )

    # --- Debugging / Zwischenausgaben ---
    dbg = p.add_argument_group(
        "Zwischenausgaben",
        "Einzelne Pipeline-Schritte als Datei speichern, um sie zu inspizieren.",
    )
    dbg.add_argument("-v", "--verbose", action="store_true", help="Ausführliche Ausgabe")
    dbg.add_argument(
        "--save-styled",
        action="store_true",
        help="Stilisiertes Binärbild speichern (<bild>.styled.png). "
             "Nützlich um Stil-Parameter (Canny-Schwellen, XDoG-σ …) zu tunen.",
    )
    dbg.add_argument(
        "--save-svg",
        action="store_true",
        help="Vektorisierte Pfade als SVG speichern (<bild>.svg). "
             "Nützlich um Pfadanzahl und --simplify-eps zu beurteilen.",
    )
    dbg.add_argument(
        "--save-gcode",
        action="store_true",
        default=True,
        help="GCode-Datei speichern (Standard: an). "
             "Auf --no-save-gcode setzen, um nur SVG/Bild zu erzeugen.",
    )
    dbg.add_argument("--no-save-gcode", dest="save_gcode", action="store_false")
    dbg.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Kurzform: aktiviert --save-styled und --save-svg zusammen.",
    )

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # --- Eingabe validieren ---
    if not args.image.exists():
        logger.error("Eingabebild nicht gefunden: %s", args.image)
        return 1

    output_path = args.output or args.image.with_suffix(".gcode")

    # --save-intermediate ist Kurzform für beide Einzel-Flags
    if args.save_intermediate:
        args.save_styled = True
        args.save_svg = True

    logger.info("=== img2gcode Pipeline gestartet ===")
    logger.info("Eingabe      : %s", args.image)
    logger.info("Ausgabe      : %s", output_path if args.save_gcode else "(deaktiviert)")
    logger.info("Zielgröße    : %.1f × %.1f mm", args.width, args.height)
    logger.info("Stil         : %s", args.style)
    logger.info(
        "Ausgaben     : %s",
        ", ".join(filter(None, [
            "styled.png" if args.save_styled else None,
            "svg"        if args.save_svg    else None,
            "gcode"      if args.save_gcode  else None,
        ])),
    )

    # ------------------------------------------------------------------ #
    # Schritt 1: Stilisierung                                             #
    # ------------------------------------------------------------------ #
    logger.info("--- Schritt 1: Stilisierung ---")
    binary_image = stylise_image(args)

    if args.save_styled:
        styled_path = args.image.with_suffix(".styled.png")
        import cv2
        cv2.imwrite(str(styled_path), binary_image)
        logger.info("Stilisiertes Bild gespeichert : %s", styled_path)

    # ------------------------------------------------------------------ #
    # Schritt 2: Vektorisierung                                           #
    # ------------------------------------------------------------------ #
    logger.info("--- Schritt 2: Vektorisierung ---")
    paths = vectorise(binary_image, min_path_px=args.min_path_px, simplify_eps=args.simplify_eps)
    logger.info("  %d Pfade extrahiert", len(paths))

    if args.save_svg:
        svg_path = args.image.with_suffix(".svg")
        paths_to_svg(paths, image_shape=binary_image.shape[:2], output_path=svg_path)
        logger.info("SVG gespeichert               : %s", svg_path)

    # ------------------------------------------------------------------ #
    # Schritt 3: GCode-Generierung                                        #
    # ------------------------------------------------------------------ #
    logger.info("--- Schritt 3: GCode-Generierung ---")
    gcode_lines = generate_gcode(
        paths=paths,
        image_shape=binary_image.shape[:2],  # (h, w)
        target_width_mm=args.width,
        target_height_mm=args.height,
        origin_x=args.origin_x,
        origin_y=args.origin_y,
        keep_aspect=args.keep_aspect,
        feedrate_draw=args.feedrate_draw,
        feedrate_travel=args.feedrate_travel,
        pen_down_cmd=args.pen_down_cmd,
        pen_up_cmd=args.pen_up_cmd,
        pen_delay_ms=args.pen_delay_ms,
    )
    logger.info("  %d GCode-Zeilen generiert", len(gcode_lines))

    if args.save_gcode:
        output_path.write_text("\n".join(gcode_lines) + "\n", encoding="utf-8")
        logger.info("GCode gespeichert             : %s", output_path)

    # ------------------------------------------------------------------ #
    # Schritt 4: Senden (optional)                                        #
    # ------------------------------------------------------------------ #
    if args.send:
        logger.info("--- Schritt 4: Senden an GRBL ---")
        send_gcode(
            gcode_lines=gcode_lines,
            port=args.port,
            baud=args.baud,
            dry_run=args.dry_run,
        )

    logger.info("=== Fertig ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
