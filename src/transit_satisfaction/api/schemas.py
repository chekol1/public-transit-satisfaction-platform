from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, examples=["The bus was on time today!"])
    source_id: str | None = Field(default=None, description="Optional upstream record id")
    user_location: str | None = Field(
        default=None,
        description="Optional free-text profile location, used as a geo-tagging "
        "fallback when the text itself names no BART/MUNI stop or city",
    )
    persist: bool = Field(default=False, description="If true, store the scored record in Mongo")


class PredictResponse(BaseModel):
    label: str
    satisfaction_score: float
    is_transit_related: bool
    municipality: str | None = None
    geo_source: str | None = None
    record_id: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    model_loaded: bool
