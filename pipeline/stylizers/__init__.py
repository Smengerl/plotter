"""
pipeline/stylizers/__init__.py — Registry aller Stilisierer

Neue Stilisierer müssen nur hier eingetragen werden — der Rest der
Pipeline (CLI, ``stylise.py``) erkennt sie automatisch.
"""

from __future__ import annotations

from pipeline.stylizers.adaptive_threshold import AdaptiveThresholdStylizer
from pipeline.stylizers.base import BaseStylizer
from pipeline.stylizers.canny import CannyStylizer
from pipeline.stylizers.dexined import DexiNedStylizer
from pipeline.stylizers.hed import HEDStylizer
from pipeline.stylizers.informative_drawings import InformativeDrawingsStylizer
from pipeline.stylizers.lineart import LineartStylizer
from pipeline.stylizers.xdog import XDoGStylizer

# Registry: CLI-Name → Klasse
_REGISTRY: dict[str, type[BaseStylizer]] = {
    CannyStylizer.name:                 CannyStylizer,
    XDoGStylizer.name:                  XDoGStylizer,
    AdaptiveThresholdStylizer.name:     AdaptiveThresholdStylizer,
    HEDStylizer.name:                   HEDStylizer,
    DexiNedStylizer.name:               DexiNedStylizer,
    LineartStylizer.name:               LineartStylizer,
    InformativeDrawingsStylizer.name:   InformativeDrawingsStylizer,
}

#: Alle verfügbaren CLI-Namen (für ``argparse choices``)
STYLE_CHOICES: list[str] = list(_REGISTRY.keys())


def get_stylizer(name: str, **kwargs: object) -> BaseStylizer:
    """
    Gibt eine instanziierte Stilisierer-Instanz für ``name`` zurück.

    Parameters
    ----------
    name   : CLI-Name (z.B. ``"canny"``, ``"xdog"``, …)
    kwargs : Werden direkt an den Konstruktor der Klasse weitergegeben

    Raises
    ------
    ValueError : Wenn ``name`` nicht in der Registry enthalten ist.

    Example
    -------
    >>> s = get_stylizer("canny", low=30, high=100, blur=5)
    >>> binary = s.stylise(Path("foto.jpg"), max_side=1024)
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unbekannte Stil-Methode: {name!r}. "
            f"Verfügbar: {', '.join(STYLE_CHOICES)}"
        )
    return cls(**kwargs)


__all__ = [
    "BaseStylizer",
    "CannyStylizer",
    "XDoGStylizer",
    "AdaptiveThresholdStylizer",
    "HEDStylizer",
    "DexiNedStylizer",
    "LineartStylizer",
    "InformativeDrawingsStylizer",
    "STYLE_CHOICES",
    "get_stylizer",
]
