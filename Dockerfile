# Multi-stage build: keep the runtime image free of build tooling.
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim AS runtime

# Run as a non-root user -- there's no reason this process needs root,
# and it's a cheap win in any security-conscious review.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY src/ ./src/

# Trained artifact is baked in for this demo image; in a real pipeline this
# would instead be pulled from an artifact store (S3/model registry) at
# startup or build time, versioned independently from the code.
COPY artifacts/ ./artifacts/

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONPATH=/app/src \
    MODEL_ARTIFACT_PATH=/app/artifacts/model.pkl

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "transit_satisfaction.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
