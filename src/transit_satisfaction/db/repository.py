"""MongoDB repository for storing scored transit-satisfaction records.

Rewritten from the original `DB_DAL.py`, which had several real problems:

- a full MongoDB connection string, *including a plaintext password*,
  hardcoded in source and committed to a public GitHub repo;
- methods defined without `self` but called as if static, while still
  mutating shared state -- fragile and hard to test;
- bare `except:` blocks that silently swallowed connection/insert errors,
  so failures were invisible;
- a collection name with a trailing-space typo (`"first_filter_DB "`).

This version pulls the connection string from environment/config only
(see `transit_satisfaction.config`), uses a real class with instance
state, is a context manager so connections are always closed, and raises
on failure instead of swallowing errors -- callers decide how to handle
it, and it shows up in logs either way.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from transit_satisfaction.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SatisfactionRecord:
    """A single scored piece of text, ready to persist."""

    text: str
    satisfaction_score: float
    label: str
    municipality: str | None = None
    geo_source: str | None = None
    source_id: str | None = None
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_document(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "satisfaction_score": self.satisfaction_score,
            "label": self.label,
            "municipality": self.municipality,
            "geo_source": self.geo_source,
            "source_id": self.source_id,
            "scored_at": self.scored_at,
        }


class SatisfactionRepository:
    """Thin repository around a single Mongo collection.

    Usage:
        with SatisfactionRepository() as repo:
            repo.add(record)

    A `MongoClient` (or a `mongomock.MongoClient` in tests) can be injected
    directly, which is what makes this testable without a real database.
    """

    COLLECTION_NAME = "satisfaction_scores"

    def __init__(self, client: MongoClient | None = None) -> None:
        self._client = client or MongoClient(settings.mongo_uri)
        self._db = self._client[settings.mongo_db_name]
        self._collection: Collection = self._db[self.COLLECTION_NAME]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SatisfactionRepository:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def add(self, record: SatisfactionRecord) -> str:
        try:
            result = self._collection.insert_one(record.to_document())
        except PyMongoError:
            logger.exception("Failed to insert satisfaction record")
            raise
        return str(result.inserted_id)

    def add_many(self, records: list[SatisfactionRecord]) -> list[str]:
        if not records:
            return []
        try:
            result = self._collection.insert_many([r.to_document() for r in records])
        except PyMongoError:
            logger.exception("Failed to bulk insert satisfaction records")
            raise
        return [str(_id) for _id in result.inserted_ids]

    def find_all(self, limit: int = 100) -> Iterator[dict[str, Any]]:
        try:
            cursor = self._collection.find({}).sort("scored_at", -1).limit(limit)
        except PyMongoError:
            logger.exception("Failed to query satisfaction records")
            raise
        yield from cursor

    def find_by_municipality(self, municipality: str, limit: int = 100) -> Iterator[dict[str, Any]]:
        try:
            cursor = (
                self._collection.find({"municipality": municipality})
                .sort("scored_at", -1)
                .limit(limit)
            )
        except PyMongoError:
            logger.exception("Failed to query satisfaction records by municipality")
            raise
        yield from cursor
