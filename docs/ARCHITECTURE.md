# Architecture

```mermaid
flowchart LR
    subgraph Client
        A[POST /predict]
    end

    subgraph API["FastAPI service (this repo)"]
        B[predict endpoint]
        C[GeoTagger]
        D[predict_satisfaction]
        E[/metrics - Prometheus/]
    end

    subgraph Model["Model artifact"]
        F[(model.pkl\nTF-IDF + LogisticRegression)]
    end

    subgraph Training["Offline training (train.py)"]
        G[sample_tweets.csv] --> H[sklearn Pipeline.fit]
        H --> F
        H --> I[model.metrics.json]
    end

    subgraph Storage
        J[(MongoDB\nsatisfaction_scores)]
    end

    subgraph Observability["monitoring/ (opt-in profile)"]
        K[Prometheus] --> L[Grafana dashboard]
    end

    A --> B
    B --> C
    B --> D
    D --> F
    B -->|persist=true| J
    B --> E
    E -.->|scrape| K
```

## Why it's shaped this way

**Training and serving are two different processes with one contract between them: the artifact.** `train.py` owns every modeling decision (features, algorithm, hyperparameters, evaluation). `predict.py` and the API know nothing about any of that -- they load a fitted `sklearn` pipeline and call `.predict_proba`. This is the same shape as an at-scale setup where a data science team retrains and versions a model independently of the team that operates the serving layer; the interface between them is deliberately thin.

**The DB layer is optional and non-blocking.** `/predict` always returns a score even if Mongo is down -- persistence is opt-in per request (`persist: true`) and failures are caught and logged rather than surfaced as a 500. A scoring endpoint going down because a downstream write failed is a worse failure mode than losing one row.

**Everything reads config from the environment**, never from source. This was the single biggest problem in the original project (a MongoDB URI with a plaintext password, and Twitter API keys, both committed to a public repo).

## What's out of scope on purpose

- **Real-time ingestion.** The original project streamed tweets directly via threads writing to local files. A production version of that would be Kafka/Kinesis, not threads -- but that's a separate ingestion service, not part of this API's job.
- **A fancier model.** TF-IDF + Logistic Regression is intentionally boring: it trains in under a second on a laptop with no GPU and no external model download, so the whole pipeline is reproducible by anyone who clones the repo. Swapping in fastText embeddings or a transformer is a change entirely inside `train.py` -- the API and tests wouldn't need to change.
- **A real geo lookup.** `GeoTagger` is a substring match against a small list. The original project's `muni.json` had full municipality coverage; that's a drop-in data file, not an architecture change.
