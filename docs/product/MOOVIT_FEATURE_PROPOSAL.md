# Transit Line Satisfaction — Moovit Feature Proposal

Role framing for this doc: Lead PM + Senior SWE for sections A/B/D, Principal
System Architect + Lead ML Engineer for section C. Grounded in the actual
working pipeline in this repo (real BART/MUNI geo-tagging, a relevance
filter, a versioned ML artifact contract -- see `docs/ARCHITECTURE.md` and
`docs/MODEL_DECISIONS.md`), reimagined as a feature inside a real transit
app rather than a standalone API.

## A. Feature Context & Problem Statement

**Target app:** Moovit (transit & urban mobility).

**Feature concept:** Score public sentiment/comfort per transit line in
near-real-time from social text (and, critically, Moovit's own first-party
crowd-sourced signal -- see the data-sources note below), surfaced visually
in-app as part of route planning and live trip tracking.

**Core problem:** Two riders comparing Line 14 vs. Line 49 to the same
destination today only see schedule and crowding-by-GTFS-RT-occupancy data.
Neither tells them "Line 14 has had three complaints about a broken AC and
a skipped stop in the last hour" -- information that's out there in public
social chatter and in-app feedback, just not surfaced.

**Target audience:** daily commuters (route choice), tourists (unfamiliar
system, no baseline expectations to compare against), accessibility-focused
riders (a *specific*, high-value audience: complaints about broken
elevators, non-functioning ramps, or announcement systems are exactly the
kind of low-volume-but-high-severity signal a generic occupancy sensor
never captures, but that shows up in text).

**Explicit non-goal:** this is a *decision-support signal*, not a safety or
compliance system. It must never be the sole basis for an accessibility
claim ("elevator is broken") without corroboration -- see moderation/edge
cases in section C.

## B. Product Specification

### User stories
1. *As a commuter comparing two route options*, I see a small
   color-coded satisfaction indicator next to each line in the results
   list, so I can factor "how's it actually going right now" into my
   choice without leaving the search screen.
2. *As a rider on an active trip*, I can tap through to a line detail view
   showing a rolling satisfaction trend (last 2h) and a handful of recent,
   moderated feedback snippets, so I understand *why* the score is what it
   is, not just a bare number.
3. *As an accessibility-focused rider*, I can filter/see a distinct
   "accessibility issues reported" flag separate from general comfort
   sentiment, so a low general-comfort score (crowded, but otherwise fine)
   doesn't bury a "elevator out of service" signal that matters more to me.
4. *As a tourist*, I see the score with no assumed context -- a tooltip
   explains what it means and how many reports it's based on, since I have
   no baseline for what "normal" looks like on this system.

### UX surfaces
- **Route results list:** a small colored dot/chip per line option (green
  / amber / red / grey-for-"insufficient data"), not a numeric score --
  low cognitive load, glanceable while comparing 3-5 options.
- **Line detail view (this is the "dashboard" the demo web page mocks
  up):** the current score with confidence/sample-size, a rolling trend
  sparkline, an aspect breakdown (comfort / punctuality / crowding /
  accessibility -- not one blended number), and 3-5 recent moderated
  snippets with relative timestamps and source attribution ("from a public
  post" / "from a Moovit rider").
- **Map overlay:** route lines colored by current satisfaction, consistent
  with the results-list color coding, for the "which line looks bad right
  now" glanceable view while looking at the map.

### Explicit non-goals for v1
- Not a replacement for GTFS-RT occupancy/delay data -- an additive signal
  shown alongside it, never instead of it.
- Not real-time-per-vehicle (per-*line* aggregation only in v1 -- per
  individual bus/train is a stretch goal once volume justifies it,
  see roadmap).
- Not multi-language in v1 (see roadmap phase 3).

## C. Technical Architecture & System Design

### Data sources & APIs

| Source | Role | Real-world caveat |
|---|---|---|
| **GTFS (static)** | Route/stop/line identity -- the join key everything else hangs off | Needs a per-agency ingestion + normalization job; agencies publish inconsistently |
| **GTFS-RT** | Vehicle positions, existing occupancy/delay signal | Already Moovit's core data; this feature augments it, doesn't replace it |
| **Moovit first-party crowd-sourced feedback** | "How was your ride?" / crowdedness prompts Moovit already collects | **This should be the primary signal, not social media.** It's opt-in, line-attributed by construction (the rider is *on* that line), and not subject to a third-party API's pricing/access changes. |
| **X (Twitter) filtered stream** | Supplementary public-sentiment signal | The original 2020-era project assumed cheap/free firehose access. **That's no longer true**: since 2023, meaningful filtered-stream read access sits behind paid API tiers (pricing has moved around; budget for a real recurring line item, not a free integration, and treat any given tier's request budget as one more caching/rate-limit constraint to design around, not an afterthought). Design the ingestion service so X is a *pluggable, disable-able* source -- the feature must degrade gracefully to first-party-only, not fail, if this feed is throttled, removed, or priced out. |
| **Other public social sources (optional, later)** | e.g. a local subreddit, a city 311-style feed | Same "pluggable source" treatment as X -- one more ingestion adapter behind the same interface, not a special case |

### High-level system design (microservices)

```mermaid
flowchart TB
    subgraph Ingestion["Ingestion services (independently deployable, independently rate-limited)"]
        I1[Moovit first-party feedback ingester]
        I2[Social listening ingester\n(X API, pluggable/disable-able)]
        I3[GTFS/GTFS-RT sync service]
    end

    subgraph Stream["Event backbone"]
        K[(Kafka / Kinesis topic:\nraw-transit-mentions)]
    end

    subgraph Processing["NLP / scoring services"]
        R[Relevance filter service]
        G[Geo/line resolution service\n(BART/MUNI-style cascade, generalized\nto GTFS stop/line matching)]
        M[Moderation / spam-abuse filter]
        S[Satisfaction + aspect scoring service]
    end

    subgraph Serving["Aggregation & serving"]
        AG[Aggregation service\n(rolling per-line/per-aspect windows)]
        CACHE[(Redis: current per-line scores)]
        TS[(Time-series store:\nhistorical trend)]
        API[Public API / BFF]
    end

    I1 --> K
    I2 --> K
    I3 -.->|line/stop reference data| G

    K --> R --> G --> M --> S --> AG
    AG --> CACHE
    AG --> TS
    CACHE --> API
    TS --> API
    API -->|SSE: live score updates| Client[Moovit app]
    API -->|REST: line detail, trend, snippets| Client
```

Each ingestion adapter is a separate deployable unit behind a common
`raw-transit-mentions` event schema -- adding/removing a source (or an
entire third-party API going away) is a config change to the event
backbone, not a rewrite of the scoring pipeline. This is the concrete
"microservices" answer: the boundary is drawn at *independently-scaling,
independently-failing* concerns (an X API outage/rate-limit shouldn't
touch the Moovit-first-party path at all), not at "one service per file."

### The ML-modernization angle ("futuristic, AI-wise")

The honest modernization path, in order of what actually changes the
accuracy ceiling vs. what's just fashionable:

1. **Aspect-based scoring, not one blended number.** "Comfortable but
   late" and "on time but filthy" are both currently invisible under a
   single satisfaction score. Splitting into aspects (comfort /
   punctuality / crowding / accessibility) is a labeling and evaluation
   change, not a modeling change -- do this before touching the model.
2. **LLM-as-labeler, small-model-in-production.** Rather than either (a)
   staying on a from-scratch TF-IDF baseline forever, or (b) calling a
   hosted LLM on every production request (real per-request cost and
   latency at Moovit's volume), use a hosted LLM offline to produce
   high-quality aspect-labeled training data from a sample of real
   mentions, then distill that into a small, fast, cheap production model
   (a fine-tuned small transformer or even a well-featured classical
   model) evaluated against the LLM-labeled set. This is the real, current
   (not just buzzword) pattern for exactly this kind of problem: expensive
   judgment used to bootstrap labels, cheap model used to serve traffic.
3. **A real model registry once there's more than one artifact worth
   comparing** (MLflow or equivalent) -- promotion/rollback between the
   TF-IDF baseline and each distilled successor, evaluated on the same
   held-out set, not a leap of faith.

None of this requires an LLM in the request path at serving time, which
matters for both cost and the SSE-latency budget below.

### Real-time delivery: SSE, not WebSocket

The client only needs server -> client score pushes (a rider watching a
line's score update while planning/riding); there's no client -> server
real-time payload in this feature. **Server-Sent Events** is the leaner
choice: plain HTTP (works through existing infra/CDNs with less friction
than WebSocket upgrade handshakes), built-in reconnect semantics, and one
fewer protocol for the mobile client to maintain. Reserve WebSocket for a
later feature that's genuinely bidirectional (e.g., live in-app chat
between riders) -- don't adopt it here just because it sounds more
"real-time."

### Example API payloads

`GET /v1/lines/{line_id}/satisfaction`
```json
{
  "line_id": "sfmta:14",
  "current_score": 0.61,
  "confidence": "medium",
  "sample_size_last_hour": 23,
  "aspects": {
    "comfort": 0.58,
    "punctuality": 0.42,
    "crowding": 0.70,
    "accessibility": null
  },
  "trend_2h": [0.55, 0.58, 0.60, 0.61],
  "as_of": "2026-07-22T18:42:00Z"
}
```

`GET /v1/lines/{line_id}/feedback?limit=5`
```json
{
  "line_id": "sfmta:14",
  "items": [
    {
      "text_snippet": "Bus was pretty crowded but on time today",
      "aspect": "crowding",
      "sentiment": "mixed",
      "source": "public_post",
      "relative_time": "12m ago"
    },
    {
      "text_snippet": "Elevator at the stop is out again",
      "aspect": "accessibility",
      "sentiment": "negative",
      "source": "moovit_rider",
      "relative_time": "38m ago",
      "flagged_for_review": false
    }
  ]
}
```

`SSE` stream event (`text/event-stream`, one line's subscription):
```
event: score_update
data: {"line_id":"sfmta:14","current_score":0.63,"as_of":"2026-07-22T18:44:00Z"}
```

### Edge cases & failure handling

| Scenario | Behavior |
|---|---|
| Low client connectivity | Client caches last-known score + `as_of` timestamp locally; UI shows "as of 14 min ago" staleness label rather than a stale number presented as live |
| Inaccurate/missing GPS | Fall back to schedule-based line matching (which line is the user's search/trip against) rather than proximity-based inference |
| Missing/incomplete agency GTFS data | Show "no data for this line" explicitly -- never fabricate a score from an unrelated line's data |
| Low-volume line / off-peak, sparse mentions | Minimum sample-size threshold before showing a score at all; below it, show "insufficient data" (grey), not a noisy score from 2 mentions |
| Third-party social API throttled, priced out, or removed | Ingestion adapter degrades to first-party-feedback-only; aggregation service has no hard dependency on any single source being present |
| Spam / brigading / bot activity skewing a line's score | Moderation service between geo-resolution and scoring; rate-limit-per-account signal contribution, not just per-mention |
| Multi-language mentions (non-English cities) | v1 explicitly scoped English-only (see roadmap); non-English mentions are geo-tagged and stored but excluded from scoring until a multilingual model ships, not silently mis-scored |
| Ambiguous line/stop name collision (e.g., a street name matches a stop *and* a generic word) | Same tiered-confidence approach as this repo's existing `GeoTagger`/`geo_source` field -- expose *which* tier resolved a match so low-confidence resolutions can be down-weighted or hidden below a confidence floor |

## D. Implementation Roadmap

### Tech stack considerations
- **Mobile client:** this is a feature *inside* Moovit's existing app, not
  a greenfield app -- the real answer is "whatever Moovit's app is already
  built in" (not something this proposal can assert with confidence from
  outside the company). The generic trade-off for the record: React
  Native/Flutter minimize duplicated UI logic across iOS/Android for a
  net-new feature module, at the cost of native-module bridging for any
  map-rendering performance work; a native implementation costs 2x the UI
  work but avoids that bridge entirely. Match whatever the existing app
  already uses rather than introducing a second cross-platform framework
  into one app.
- **Backend:** microservices per the diagram above, event-driven via
  Kafka/Kinesis, deployed on the same Kubernetes/EKS-style infra this repo
  already has Terraform/k8s manifests for -- each service in the diagram
  maps to one deployable unit with its own scaling policy (the ingestion
  services scale on source-API rate limits; the scoring service scales on
  event volume; these are *not* the same scaling curve, which is exactly
  why they're separate services).
- **Real-time:** SSE (see above), not WebSocket.

### Sprint execution phases

**Phase 1 -- MVP (single-city pilot):**
- One city (e.g., San Francisco, matching this repo's existing real
  BART/MUNI geo-tagging work), English only.
- Moovit first-party feedback as the *only* signal -- no third-party
  social API cost/dependency yet, proves the UX and aggregation logic
  cheaply.
- Single blended score (no aspect split yet), polled not pushed (skip SSE
  infrastructure for the pilot).
- Existing TF-IDF+LogisticRegression-class baseline model (this repo's
  actual current approach) -- ship the simplest thing that's honestly
  evaluated, not the fanciest thing that isn't.

**Phase 2 -- Beta (multi-city, real-time, aspect scoring):**
- Add SSE push, add the aspect breakdown (comfort/punctuality/crowding/
  accessibility), add moderation service.
- Introduce the X/social ingestion adapter as a genuinely optional,
  disable-able source -- budget its cost explicitly rather than assuming
  it's free.
- Begin the LLM-as-labeler distillation pass for a second-generation
  scoring model, evaluated against the phase-1 baseline on a held-out set
  before any promotion decision.

**Phase 3 -- GA rollout (scale-out):**
- Multi-language scoring.
- Per-vehicle (not just per-line) granularity where volume justifies it.
- Full model registry with promotion/rollback; SLO-backed monitoring and
  alerting on each microservice independently (an ingestion outage and a
  scoring-service outage should page differently, since they degrade the
  feature differently).
