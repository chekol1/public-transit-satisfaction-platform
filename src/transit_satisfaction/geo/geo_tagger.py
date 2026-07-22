"""Transit-stop / location tagging for free-text mentions.

Reimplements the spirit of the original project's `geo_extract.py`: a
cascade of geo-resolution tiers, most-specific first. The original ran this
against real San Francisco Bay Area transit data (BART stations, MUNI
stops, tweet GPS coordinates, tweet place bounding boxes, user profile
location) via Excel-file lookups and global mutable counters; this version
keeps the same tiered idea -- BART station -> MUNI stop -> generic city
mention -> user profile location -- as a small, testable, in-memory lookup,
dropping only the tiers that depended on live tweet fields (GPS
coordinates, `place` bounding box) or a building-name Excel sheet this
rebuild doesn't have.

`muni_stops.json` is the original project's real MUNI stop GeoJSON,
vendored as-is (public transit-stop data, no credentials). `bart_stations.json`
is a curated list of real BART station names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BART_STATIONS_PATH = Path(__file__).parent / "bart_stations.json"
DEFAULT_MUNI_STOPS_PATH = Path(__file__).parent / "muni_stops.json"

SF_MENTION_KEYWORDS = ("san francisco", "bay area", " sf ", " sf,", " sf.")
USER_LOCATION_KEYWORDS = ("san francisco", "sf", "bay area")


@dataclass
class GeoMatch:
    """A resolved location plus which tier resolved it.

    Mirrors the original project's `kind` column: callers see *how
    confidently* a location was resolved (an exact BART/MUNI stop name vs.
    a loose city mention vs. a user-profile fallback) instead of a bare
    string with no provenance.
    """

    name: str
    source: str  # "bart" | "muni" | "text" | "user_location"


class GeoTagger:
    def __init__(
        self,
        bart_stations: list[str] | None = None,
        muni_stops: list[str] | None = None,
    ) -> None:
        self._bart_stations = bart_stations or self._load_bart_stations()
        self._muni_stops = muni_stops or self._load_muni_stops()

    @staticmethod
    def _load_bart_stations() -> list[str]:
        with DEFAULT_BART_STATIONS_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_muni_stops() -> list[str]:
        with DEFAULT_MUNI_STOPS_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        # The raw GeoJSON has one feature per physical stop pole, so the
        # same stop name repeats many times -- dedupe before matching.
        return sorted({feature["properties"]["stop_name"] for feature in data["features"]})

    def tag(self, text: str, user_location: str | None = None) -> GeoMatch | None:
        """Resolve a location from free text, tiered most-specific first.

        Tiers, in order: an explicit BART station name, a MUNI stop name, a
        generic San Francisco / Bay Area mention in the text itself, then a
        user profile location field mentioning the Bay Area -- the same
        fallback order the original project used, minus the tweet-specific
        tiers (GPS coordinates, `place` bounding box) that don't apply here.
        """
        lowered = text.lower()

        for station in self._bart_stations:
            if station.lower() in lowered:
                return GeoMatch(name=station, source="bart")

        for stop in self._muni_stops:
            if stop.lower() in lowered:
                return GeoMatch(name=stop, source="muni")

        padded = f" {lowered} "
        if any(keyword in padded for keyword in SF_MENTION_KEYWORDS):
            return GeoMatch(name="San Francisco", source="text")

        if user_location:
            lowered_location = user_location.lower()
            if any(keyword in lowered_location for keyword in USER_LOCATION_KEYWORDS):
                return GeoMatch(name="San Francisco", source="user_location")

        return None
