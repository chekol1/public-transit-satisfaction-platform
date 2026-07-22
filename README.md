# Transit Satisfaction Platform

A small production-style service that scores public-transit-related text
for rider satisfaction, and stores the results for later analysis.

This is a rebuild of an earlier academic project ([original
repo](https://github.com/ronhadad22/LEVEL-OF-USER-SATISFACTION-FOR-PUBLIC-TRANSPORTATION-USING-DATA-MINING-AND-ML)):
tweet streaming + geo-tagging + fastText vectors + a RandomForest
classifier + MongoDB, spread across a dozen loosely-connected scripts with
hardcoded MongoDB and Twitter credentials committed to source control.

This version keeps the same idea (score text for satisfaction, tag it
with a location, store it) but rebuilt as a small, testable, deployable
service: a clean `sklearn` pipeline behind a versioned artifact, a FastAPI
serving layer, a repository-pattern DB layer, containerized, with
Terraform + Kubernetes manifests to run it on EKS, a CI pipeline, and
Prometheus metrics with a provisioned Grafana dashboard. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture and the
reasoning behind it, and [`docs/MODEL_DECISIONS.md`](docs/MODEL_DECISIONS.md)
for what the original project tried modeling-wise and why this rebuild
chose differently.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

make train   # writes artifacts/model.pkl + artifacts/model.metrics.json
make test    # 14 tests: ML pipeline, DB repository (mongomock), API, geo-tagging
make run     # http://localhost:8000/docs
```

Or with Docker:

```bash
make train          # bake a model artifact in before building the image
docker compose up --build
```

For the full observability stack (Prometheus + Grafana) alongside the API:

```bash
docker compose --profile monitoring up --build
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (anonymous viewer access, or admin/admin)
```

Try it:

```bash
curl -X POST localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Bus was on time and clean today near Embarcadero station"}'
# {"label":"satisfied","satisfaction_score":0.54,"is_transit_related":true,"municipality":"Embarcadero","geo_source":"bart","record_id":null}
```

## What's here

| Layer | Where | Notes |
|---|---|---|
| ML training | `src/transit_satisfaction/ml/train.py` | TF-IDF + Logistic Regression, versioned artifact + metrics |
| Serving | `src/transit_satisfaction/ml/predict.py` | Loads the artifact, nothing model-specific here |
| API | `src/transit_satisfaction/api/` | FastAPI: `/predict`, `/health`, `/metrics` |
| Geo-tagging | `src/transit_satisfaction/geo/` | Tiered BART station -> MUNI stop -> city mention -> user-location cascade, using the original project's real `muni.json` |
| Relevance filter | `src/transit_satisfaction/nlp/relevance.py` | Is the text even about public transit? (the original's missing `analays_tweets.py` step) |
| Storage | `src/transit_satisfaction/db/repository.py` | MongoDB repository, testable via `mongomock`, non-blocking on the API |
| Infra | `infra/terraform/`, `infra/k8s/` | ECR + EKS (Fargate profile) + Deployment/Service/HPA |
| Monitoring | `monitoring/` | Prometheus scrape config + provisioned Grafana dashboard (request rate, latency p50/p95, target up) |
| CI | `.github/workflows/ci.yml` | lint (ruff/black) -> test (pytest) -> terraform fmt/validate -> build & push to ECR |

## Security note

The original project had a live MongoDB connection string (with password)
and Twitter API keys committed in plaintext. This rewrite reads all of
that from environment variables only (see `.env.example`) -- nothing
resembling a real credential should ever be a default value in
`config.py`.

## What I'd do with more time

- Real-time ingestion via Kafka/Kinesis instead of the original's
  file-polling threads.
- Model registry (MLflow) instead of a single artifact path, so multiple
  model versions can be compared/rolled back.
- External Secrets Operator to pull the Mongo URI from AWS Secrets
  Manager into the cluster instead of a plain Kubernetes Secret.
- Swap TF-IDF for the original's fastText embeddings, or a small
  transformer, once there's a real labeled dataset to justify it.
