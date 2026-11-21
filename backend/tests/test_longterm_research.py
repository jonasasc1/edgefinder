"""Forschungsskript Langfrist: Zusammensetzung des Gesamtscores (bekannte Werte, Grenzfälle)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from longterm_research import combine

COMPS = {"macro": (0.5, 0.4), "trend": (-0.5, 0.2), "cot": (None, 0.4)}


def test_combine_renormiert_ohne_fehlende_faktoren():
    assert round(combine(COMPS), 6) == round(10 * (0.5 * 0.4 - 0.5 * 0.2) / 0.6, 6)


def test_combine_flip_und_gewicht():
    assert round(combine(COMPS, flip=("macro",)), 6) == round(
        10 * (-0.5 * 0.4 - 0.5 * 0.2) / 0.6, 6
    )
    assert round(combine(COMPS, mult={"macro": 0.5}), 6) == round(
        10 * (0.5 * 0.2 - 0.5 * 0.2) / 0.4, 6
    )


def test_combine_leer():
    assert combine({"cot": (None, 1.0)}) is None
