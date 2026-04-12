# Stylizers

Dieses Verzeichnis enthält mehrere Stilisierer ("stylizers"), die ein Eingangsbild
in ein binäres Linienstil‑Bild (uint8, 255=Linie, 0=Hintergrund) umwandeln.

Die Implementierungen reichen von einfachen klassischen Filtern bis zu
NN‑basierten Modellen (ONNX/PyTorch). Dieser README sammelt die Varianten,
ihre Parameter, Hinweise zu Abhängigkeiten und kleine Beispiele zur Verwendung.

Kurz: Alle Stylizer implementieren die Methode `apply(gray)` und die
öffentliche API `stylise(image_path, max_side)` (siehe `BaseStylizer`).

## Verwendung (Kurz)

- In Python:

```py
from pipeline.stylizers import get_stylizer
sty = get_stylizer('xdog', sigma=0.4, threshold=0)  # threshold=0 → Otsu
binary = sty.stylise(Path('pipeline/tests/testimage.png'), max_side=512)
# binary: np.ndarray uint8 (H, W), 255=Linie
```

- Über die CLI (einige Optionen werden vom Projekt‑CLI exponiert):

```sh
python pipeline/img2gcode.py --style xdog --max-side 512 --threshold 0
```

Hinweis: viele NN‑Stilisierer haben optionale Abhängigkeiten. Wenn diese fehlen,
wirft der Konstruktor beim ersten Zugriff eine `ImportError` mit einer
Installationsanweisung.

## Liste der Stylizer

Die folgenden Stilisierer sind im Projekt registriert und über `get_stylizer(name, **kwargs)`
verfügbar. Für jede Variante sind die wichtigsten Parameter und Hinweise aufgeführt.

### canny

- Beschreibung: Klassischer Canny‑Edge‑Detector. Liefert dünne Kanten.
- Parameter:
  - `low` (int, default 50) – low threshold für Canny
  - `high` (int, default 150) – high threshold für Canny
  - `blur` (int, default 3) – Gauss‑Blur Kernel (odd)
- Verwendung: schnell, keine zusätzlichen Abhängigkeiten.

### xdog

- Beschreibung: eXtended Difference‑of‑Gaussians (Winnemöller et al.).
  Erzeugt skizzenartige dünne Linien mit einer weichen Schwelle.
- Parameter (empfohlene Defaults):
  - `sigma` (float, default 0.8) – σ für die kleinere Gauß‑Funktion (empfohlen)
  - `k_sigma` (float, default 1.6) – Verhältnis σ_big / σ_small
  - `epsilon` (float, default 0.0) – wenn 0 → adaptive Epsilon (percentile)
  - `phi` (float, default 5.0) – Steilheit der Sigmoid‑Form (empfohlen)
  - `threshold` (float, default 0.0) – finale harte Schwelle (0–255). Wenn ≤ 0 → Otsu (empfohlen)
- Hinweise / Empfehlung:
  - Die Implementierung verwendet nun per Default `epsilon=0` (adaptive eps)
    und `threshold=0` (Otsu). In Kombination mit `sigma=0.8` und `phi=5` liefert
    das robuste, gut sichtbare Linienstile auf vielen Eingangsbildern.
  - Erzeuge bei Bedarf feinere Linien durch Erhöhung von `phi` oder Verringerung
    von `sigma`; für stärkere Vereinfachung umgekehrt.
  - Setze `threshold>0` nur wenn du einen festen Binär‑Cut benötigst; ansonsten
    ist `threshold=0` (Otsu) empfehlenswert.

### adaptive

- Beschreibung: Adaptives Thresholding (OpenCV) — gut für ungleichmäßig beleuchtete Bilder.
- Parameter:
  - `block_size` (int, default 11) – Nachbarschaftsfenster (muss ungerade sein)
  - `c` (float, default 2.0) – Subtraktionskonstante
  - `method` (str, "gaussian"|"mean", default "gaussian") – adaptive Methode
  - `blur` (int, default 0) – optionaler Weichzeichner vor Threshold

### hed

- Beschreibung: Holistically‑Nested Edge Detection (HED) via ControlNet/aux detektor.
- Parameter:
  - `model_path` (Path|None) – Verzeichnis oder Datei; `None` → Auto‑Download
  - `device` (str, default "auto") – cuda > mps > cpu
  - `threshold` (int, default 128) – finale Binarisierung
- Hinweise:
  - Benötigt `controlnet_aux` + `torch` + `Pillow`.
  - Implementiert als NN‑Basisklasse; lädt das passende Preprocessor‑Modell.

### dexined

- Beschreibung: DexiNed‑Detektor (ein weiterer Edge‑Detektor). Funktional ähnlich zu HED,
  aber manchmal mit anderen Default‑Feinheiten.
- Parameter/Abhängigkeiten: wie `hed`.

### lineart

- Beschreibung: ControlNet Lineart Preprocessor (sehr saubere, dünne Linien).
- Parameter:
  - `model_path` (Path|None) – Annotators‑Gewichte oder `None` für Auto‑Download
  - `device` (str|None, default "auto") – Gerät
  - `threshold` (int, default 128) – finale Binarisierung
  - `coarse` (bool, default False) – `False` = feine Linien (sk_model.pth), `True` = grobe Linien (sk_model2.pth)
  - `detect_resolution` (int, default 512) – interne Inferenzauflösung
  - `image_resolution` (int, default 512) – Ausgabeauflösung vor Skalierung
- Hinweise:
  - Benötigt `controlnet_aux` und PyTorch. Liefert sehr präzise Kanten; ideal für technische
    Konturen und als ControlNet‑Preprocessor.

### informative

- Beschreibung: "Informative Drawings" — NN‑Generator, der semantisch wichtige Linien
  herausarbeitet (Caroline Chan et al.). Unterstützt ONNX (empfohlen) und PyTorch.
- Parameter:
  - `model_path` (Path|str|None) – Pfad zu `model.onnx` oder `model.pth`/`model2.pth`. Wenn `None`,
    wird ONNX (rocca/informative‑drawings‑line‑art‑onnx) bzw. PyTorch von Hugging Face geladen.
  - `device` (str|None, default "auto") – für PyTorch Backend
  - `threshold` (int, default 128) – finale Binarisierung (auf invertiertem Output)
  - `style` (int, 1|2, default 1) – Model‑Style
- Hinweise:
  - ONNX backend ist leichtgewichtig und bevorzugt; installiert `onnxruntime`.
  - PyTorch fallback benötigt `torch`/`torchvision` und eignet sich für GPU‑Beschleunigung.

## Allgemeine Hinweise

- Alle Stylizer geben ein uint8‑Bild zurück: 255 = Linie, 0 = Hintergrund. Das ist die
  Konvention für die nachfolgenden Schritte (`vectorise`, `gcode_gen`).
- NN‑Stilisierer laden Modelle lazy on first use und geben klare `ImportError`‑Hinweise,
  wenn optionale Abhängigkeiten fehlen (z. B. `controlnet_aux`, `onnxruntime`, `torch`).
- Parametereinstellungen beeinflussen stark das Ergebnis — bei Problemen mit leeren
  Bildern zuerst `threshold` (oder `epsilon` beim XDoG) anpassen oder Otsu/Adaptive testen.

## Tipps zum Debugging

- Prüfe schnelle Statistiken des Rückgabebilds:

```py
import numpy as np
u = np.unique(binary)
print('unique:', u, 'min', binary.min(), 'max', binary.max())
```

- Wenn das Bild nur `0` enthält → experimentiere mit folgenden Schritten:
  - XDoG: `epsilon` > 0 oder `threshold=0` (Otsu) bzw. `epsilon=0` (adaptive default)
  - Informative / Lineart / HED: prüfe, ob benötigte Pakete installiert sind; erhöhe `detect_resolution`
  - Adaptive: verkleinere `block_size` oder erhöhe `blur`

## Beispiele

- Voller Pipeline‑Durchlauf (Script `pipeline/tests/run_all_stylizers.py` nutzt diese API):

```sh
python pipeline/tests/run_all_stylizers.py --max-side 512
```

- Einzeltest in Python:

```py
from pipeline.stylizers import get_stylizer
sty = get_stylizer('lineart', device='auto', coarse=False)
bin = sty.stylise('pipeline/tests/testimage.png', max_side=512)
```

## Weiteres

- Wenn du möchtest, kann ich diese README automatisch in die Projekt‑README integrieren
  oder für jeden Stylizer ein kurzes Beispielbild im `pipeline/tests/output/` erzeugen.

---
© Projekt – Stylizers Dokumentation
