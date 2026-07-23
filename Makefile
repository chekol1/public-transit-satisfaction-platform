.PHONY: install train test lint run docker-build docker-up \
	k8s-context-guard k8s-local-build k8s-local-up k8s-local-down k8s-local-status

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

# Refuses to run unless kubectl is pointed at Docker Desktop's local
# cluster -- this machine also has an unrelated real AWS EKS context
# configured, and every k8s-local-* target below must never touch it.
k8s-context-guard:
	@ctx="$$(kubectl config current-context 2>/dev/null)"; \
	if [ "$$ctx" != "docker-desktop" ]; then \
		echo "Refusing to run: current kubectl context is '$$ctx', not 'docker-desktop'."; \
		echo "Run: kubectl config use-context docker-desktop"; \
		exit 1; \
	fi

k8s-local-build: train
	docker build -t transit-satisfaction-api:local .

k8s-local-up: k8s-context-guard k8s-local-build
	kubectl apply -k infra/k8s/local
	kubectl rollout status deployment/transit-satisfaction-api --timeout=120s

k8s-local-status: k8s-context-guard
	kubectl get pods,svc,hpa

k8s-local-down: k8s-context-guard
	kubectl delete -k infra/k8s/local --ignore-not-found
