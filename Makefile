.PHONY: install train test lint run docker-build docker-up

install:
	pip install -r requirements-dev.txt

train:
	PYTHONPATH=src python -m transit_satisfaction.ml.train

test:
	pytest

lint:
	ruff check src tests
	black --check src tests

run:
	PYTHONPATH=src uvicorn transit_satisfaction.api.main:app --reload

docker-build:
	docker build -t transit-satisfaction-api .

docker-up:
	docker compose up --build
