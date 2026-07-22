"""Transit-relevance filter.

The original project's `analays_tweets.py` filtered tweets by a keyword
list *before* running sentiment/ML scoring on them at all -- a step this
rebuild had dropped entirely, silently scoring any arbitrary text as if it
were about public transit. This reintroduces that step as a small, testable
function instead of the original's copy-pasted keyword list scattered
across three near-duplicate functions.

Keeping this a plain keyword/regex check (matching the original's actual
approach) rather than a learned classifier is a deliberate choice: it's the
same "boring first, prove the need for anything fancier" reasoning
`train.py` documents for TF-IDF + LogisticRegression over the heavier
approaches the original project explored.
"""

from __future__ import annotations

import re

# Mirrors the original project's `list_of_words` in `analays_tweets.py`,
# with "bart"/"muni" added since this rebuild is grounded in the real SF
# Bay Area transit domain (see docs/MODEL_DECISIONS.md) and those two
# system names are as relevant as the generic terms the original used.
TRANSIT_KEYWORDS = (
    "transport",
    "transportation",
    "train",
    "bus",
    "subway",
    "bart",
    "muni",
)

_KEYWORD_PATTERN = re.compile(
    r"(?:^|[^a-z])(" + "|".join(re.escape(word) for word in TRANSIT_KEYWORDS) + r")(?:[^a-z]|$)",
    re.IGNORECASE,
)


def is_transit_related(text: str) -> bool:
    """Whether `text` mentions public transit at all, by keyword match.

    Returns False for empty/whitespace-only text rather than raising --
    this is a filter, not a validator; empty text is simply not relevant.
    """
    if not text or not text.strip():
        return False
    return bool(_KEYWORD_PATTERN.search(text))
