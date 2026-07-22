import pytest
from transit_satisfaction.ml.predict import predict_satisfaction
from transit_satisfaction.ml.train import train


def test_train_produces_reasonable_metrics(tmp_path):
    artifact_path = tmp_path / "model.pkl"
    metrics = train(artifact_path=str(artifact_path))

    assert artifact_path.exists()
    assert metrics.n_samples > 0
    # Small synthetic dataset -- not aiming for SOTA, just "clearly better
    # than a coin flip" so a regression would actually fail this test.
    assert metrics.f1 > 0.6
    assert 0.0 <= metrics.roc_auc <= 1.0


def test_predict_returns_expected_shape(tmp_path):
    artifact_path = tmp_path / "model.pkl"
    train(artifact_path=str(artifact_path))

    result = predict_satisfaction(
        "The bus was on time and the driver was lovely", artifact_path=str(artifact_path)
    )

    assert result.label in {"satisfied", "unsatisfied"}
    assert 0.0 <= result.satisfaction_score <= 1.0


def test_predict_rejects_empty_text(tmp_path):
    artifact_path = tmp_path / "model.pkl"
    train(artifact_path=str(artifact_path))

    with pytest.raises(ValueError):
        predict_satisfaction("   ", artifact_path=str(artifact_path))
