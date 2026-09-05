.PHONY: dev up down logs test lint format typecheck runner tooling smoke archive

dev:
	python -m uvicorn lean_report_card.main:app --reload

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

runner:
	docker build -f runner/Dockerfile -t lean-report-card-runner:local .

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src

tooling:
	./scripts/bootstrap-submodules.sh

smoke:
	./scripts/smoke.sh

archive:
	git archive --format=tar.gz --output=lean-report-card.tar.gz HEAD
