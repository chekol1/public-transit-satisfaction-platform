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
from transit_satisfaction.nlp.relevance import is_transit_related

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

    geo_match = geo_tagger.tag(payload.text, user_location=payload.user_location)
    municipality = geo_match.name if geo_match else None
    geo_source = geo_match.source if geo_match else None

    # The model scores whatever text it's given -- it has no notion of
    # whether the text is even about public transit. `is_transit_related`
    # is exposed alongside the score rather than used to block scoring, so
    # a consumer can decide whether to trust/display an off-topic score
    # instead of us silently discarding it. A resolved BART/MUNI stop name
    # is itself strong evidence of relevance, even when the text names no
    # generic transit keyword (e.g. "Skipped my stop at 19th Ave & Holloway").
    relevant = is_transit_related(payload.text) or (geo_source in {"bart", "muni"})
    if not relevant:
        logger.debug("Scored text does not appear to be transit-related: %r", payload.text)

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
                        geo_source=geo_source,
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
        is_transit_related=relevant,
        municipality=municipality,
        geo_source=geo_source,
        record_id=record_id,
    )
