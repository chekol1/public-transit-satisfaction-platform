"""Municipality tagging for free-text mentions.

The original project (`geo_extract.py` / `geo_fi.py` / `muni.json`) matched
tweet text/location fields against a lookup of Israeli municipalities. This
is a smaller, self-contained reimplementation of the same idea: a plain
dict lookup with simple substring matching, kept behind a class so the
matching strategy (substring today, could be a proper NER/geocoder later)
can change without touching callers.

`municipalities.json` ships a small demo list; swap in the original
`muni.json` for full coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_MUNICIPALITIES_PATH = Path(__file__).parent / "municipalities.json"


class GeoTagger:
    def __init__(self, municipalities: list[str] | None = None) -> None:
        self._municipalities = municipalities or self._load_default()

    @staticmethod
    def _load_default() -> list[str]:
        with DEFAULT_MUNICIPALITIES_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    def tag(self, text: str) -> str | None:
        """Return the first municipality name found as a substring of `text`,
        or None if no match. Case-insensitive.
        """
        lowered = text.lower()
        for municipality in self._municipalities:
            if municipality.lower() in lowered:
                return municipality
        return None
