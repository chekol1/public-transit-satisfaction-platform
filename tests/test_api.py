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
    assert body["is_transit_related"] is True


def test_predict_tags_known_bart_station(client):
    resp = client.post("/predict", json={"text": "Bus delayed again near Embarcadero station"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["municipality"] == "Embarcadero"
    assert body["geo_source"] == "bart"


def test_predict_falls_back_to_user_location(client):
    resp = client.post(
        "/predict",
        json={"text": "Delayed again this morning", "user_location": "San Francisco, CA"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["municipality"] == "San Francisco"
    assert body["geo_source"] == "user_location"


def test_predict_flags_unrelated_text(client):
    resp = client.post("/predict", json={"text": "I made pasta for dinner tonight"})
    assert resp.status_code == 200
    assert resp.json()["is_transit_related"] is False


def test_predict_treats_resolved_stop_name_as_relevant(client):
    # No generic transit keyword ("bus"/"train"/etc.) in this text at all --
    # but it names a real MUNI stop, which is itself evidence of relevance.
    resp = client.post("/predict", json={"text": "Skipped my stop at 19th Avenue & Holloway St"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["geo_source"] == "muni"
    assert body["is_transit_related"] is True


def test_predict_empty_text_rejected_by_schema(client):
    resp = client.post("/predict", json={"text": ""})
    assert resp.status_code == 422


def test_metrics_endpoint_exposes_prometheus_format(client):
    client.post("/predict", json={"text": "great ride today"})
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"predictions_total" in resp.content
