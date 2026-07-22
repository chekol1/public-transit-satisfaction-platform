"""Serving-side wrapper around the trained artifact.

This is deliberately dumb: load a fitted pipeline, call `.predict_proba`,
map to a label. All the modeling decisions live in `train.py`; this module
should never need to change when the model changes, only when the output
*contract* changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from transit_satisfaction.config import settings

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    pass


@dataclass
class PredictionResult:
    label: str
    satisfaction_score: float  # probability of the "satisfied" class, 0-1


@lru_cache(maxsize=1)
def load_model(artifact_path: str | None = None) -> Pipeline:
    path = Path(artifact_path or settings.model_artifact_path)
    if not path.exists():
        raise ModelNotLoadedError(
            f"No model artifact at {path}. Run `python -m transit_satisfaction.ml.train` first."
        )
    logger.info("Loading model artifact from %s", path)
    return joblib.load(path)


def predict_satisfaction(text: str, artifact_path: str | None = None) -> PredictionResult:
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    model = load_model(artifact_path)
    proba = model.predict_proba([text])[0]
    # class 1 = "satisfied" in the training data
    score = float(proba[1])
    label = "satisfied" if score >= 0.5 else "unsatisfied"
    return PredictionResult(label=label, satisfaction_score=round(score, 4))
