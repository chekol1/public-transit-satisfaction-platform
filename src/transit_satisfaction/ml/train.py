"""Train the satisfaction classifier and save a versioned artifact.

Rewritten from `applying_ML_algorithms.py`, which:
- trained a RandomForestClassifier on pre-vectorized (fastText) CSVs that
  only existed on the original author's machine, so the pipeline couldn't
  be run or verified by anyone else;
- had no train/serve contract -- vectorization, training and inference
  were tangled together across several scripts (`convert_to_vec.py`,
  `prepare_model_fasttest.py`, `applying_ML_algorithms.py`);
- printed metrics to stdout with no record of what artifact they belong to.

This version is a single `sklearn.Pipeline` (TF-IDF -> Logistic
Regression) trained end-to-end from raw text, which means:
- there's exactly one artifact (`model.pkl`) that IS the contract between
  training and serving -- `predict.py` just loads it and calls `.predict`;
- it's reproducible from `python -m transit_satisfaction.ml.train` with no
  external API keys or a live Twitter stream;
- metrics are written alongside the artifact so you always know how the
  model currently in production was evaluated.

Swap in a fastText/transformer-based pipeline later without changing the
serving code, as long as it's still a fitted sklearn-compatible estimator
with `.predict` / `.predict_proba`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from transit_satisfaction.config import settings

logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "sample_tweets.csv"


@dataclass
class TrainingMetrics:
    trained_at: str
    n_samples: int
    f1: float
    roc_auc: float
    cv_f1_mean: float
    cv_f1_std: float
    sklearn_version: str


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.95)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def train(data_path: Path = DEFAULT_DATA_PATH, artifact_path: str | None = None) -> TrainingMetrics:
    artifact_path = artifact_path or settings.model_artifact_path

    df = pd.read_csv(data_path)
    if not {"text", "label"}.issubset(df.columns):
        raise ValueError("Training data must have 'text' and 'label' columns")

    x_train, x_test, y_train, y_test = train_test_split(
        df["text"], df["label"], test_size=0.25, random_state=42, stratify=df["label"]
    )

    pipeline = build_pipeline()
    pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_test)
    y_proba = pipeline.predict_proba(x_test)[:, 1]

    cv_scores = cross_val_score(build_pipeline(), df["text"], df["label"], cv=3, scoring="f1")

    metrics = TrainingMetrics(
        trained_at=datetime.now(timezone.utc).isoformat(),
        n_samples=len(df),
        f1=float(f1_score(y_test, y_pred)),
        roc_auc=float(roc_auc_score(y_test, y_proba)),
        cv_f1_mean=float(cv_scores.mean()),
        cv_f1_std=float(cv_scores.std()),
        sklearn_version=sklearn.__version__,
    )

    # Refit on the full dataset before shipping -- the train/test split above
    # is only for honest metrics, not for the artifact we actually serve.
    final_pipeline = build_pipeline()
    final_pipeline.fit(df["text"], df["label"])

    out_path = Path(artifact_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_pipeline, out_path)

    metrics_path = out_path.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(asdict(metrics), indent=2))

    logger.info("Model trained: %s", metrics)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = train()
    print(json.dumps(asdict(result), indent=2))
