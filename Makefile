.PHONY: site score rescore test lint format typecheck tooling archive

site:
	python3 -m http.server 8080 --directory site

score:
	python3 scripts/score_palomar.py

rescore:
	python3 scripts/score_palomar.py --rescore-existing

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy lean_report_card

tooling:
	./scripts/bootstrap-submodules.sh

archive:
	git archive --format=tar.gz --output=lean-report-card.tar.gz HEAD
