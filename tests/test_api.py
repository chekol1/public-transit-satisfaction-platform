import pytest
from fastapi.testclient import TestClient
from transit_satisfaction.ml.train import train


@pytest.fixture(scope="module", autouse=True)
def trained_model():
    # Writes to the default settings.model_artifact_path so the app (which
    # loads the model with no explicit path) can find it.
    train()
    yield


@pytest.fixture()
def client():
    from transit_satisfaction.api.main import app

    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_predict_happy_path(client):
    resp = client.post("/predict", json={"text": "Bus was on time and clean"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in {"satisfied", "unsatisfied"}
    assert 0.0 <= body["satisfaction_score"] <= 1.0


def test_predict_tags_known_municipality(client):
    resp = client.post("/predict", json={"text": "Bus delayed again in Tel Aviv"})
    assert resp.status_code == 200
    assert resp.json()["municipality"] == "Tel Aviv"


def test_predict_empty_text_rejected_by_schema(client):
    resp = client.post("/predict", json={"text": ""})
    assert resp.status_code == 422


def test_metrics_endpoint_exposes_prometheus_format(client):
    client.post("/predict", json={"text": "great ride today"})
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"predictions_total" in resp.content
