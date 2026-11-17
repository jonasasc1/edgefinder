"""Label zu einem Gesamtscore (Schwellen in config.yaml unter scoring.labels)."""

from __future__ import annotations

from edgefinder.config import ScoringConfig


def label_for(score: float, scoring: ScoringConfig) -> str:
    return scoring.label_for(score)
