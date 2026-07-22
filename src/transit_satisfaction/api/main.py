"""FastAPI service: the serving layer the DS team's model lives behind.

Contract with the ML side: whoever owns `transit_satisfaction.ml.train`
(or a future, fancier training pipeline) only needs to produce a fitted
sklearn-compatible pipeline at `settings.model_artifact_path`. Everything
in this file is agnostic to what that model actually is.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from transit_satisfaction.api.schemas import HealthResponse, PredictRequest, PredictResponse
from transit_satisfaction.db.repository import SatisfactionRecord, SatisfactionRepository
from transit_satisfaction.geo.geo_tagger import GeoTagger
from transit_satisfaction.logging_config import configure_logging
from transit_satisfaction.ml.predict import ModelNotLoadedError, load_model, predict_satisfaction

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast at startup rather than on the first request, and so
    # readiness probes can tell real model-missing failures apart from a
    # cold cache.
    try:
        load_model()
    except ModelNotLoadedError:
        logger.warning("No model artifact found at startup; /predict will 503 until one exists.")
    yield


app = FastAPI(title="Transit Satisfaction API", version="0.1.0", lifespan=lifespan)
geo_tagger = GeoTagger()

PREDICTIONS_TOTAL = Counter("predictions_total", "Number of prediction requests", ["label"])
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Time spent scoring a request")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        load_model()
        model_loaded = True
    except ModelNotLoadedError:
        model_loaded = False
    return HealthResponse(status="ok", model_loaded=model_loaded)


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    with PREDICTION_LATENCY.time():
        try:
            result = predict_satisfaction(payload.text)
        except ModelNotLoadedError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    PREDICTIONS_TOTAL.labels(label=result.label).inc()
    municipality = geo_tagger.tag(payload.text)

    record_id = None
    if payload.persist:
        try:
            with SatisfactionRepository() as repo:
                record_id = repo.add(
                    SatisfactionRecord(
                        text=payload.text,
                        satisfaction_score=result.satisfaction_score,
                        label=result.label,
                        municipality=municipality,
                        source_id=payload.source_id,
                    )
                )
        except Exception:
            # Persistence is best-effort: a DB outage shouldn't take the
            # scoring endpoint down with it. Log it, degrade gracefully.
            logger.exception("Failed to persist prediction; returning result anyway")

    return PredictResponse(
        label=result.label,
        satisfaction_score=result.satisfaction_score,
        municipality=municipality,
        record_id=record_id,
    )
