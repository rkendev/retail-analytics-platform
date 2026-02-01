.PHONY: install test test-unit test-integration lint type-check format run-local dbt-run dbt-test dbt-docs docker-build docker-run clean

# ── Setup ──────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt -r requirements-dev.txt
	pre-commit install

# ── Quality ────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/ --ignore-missing-imports

# ── Tests ──────────────────────────────────────────────────────────
test: test-unit

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short -m integration

test-all:
	pytest tests/ -v --tb=short

# ── Pipeline ───────────────────────────────────────────────────────
run-local:
	python -m src.pipeline --config configs/dev.yaml

run-dry:
	python -m src.pipeline --config configs/dev.yaml --dry-run

# ── dbt ────────────────────────────────────────────────────────────
dbt-deps:
	cd dbt_retail && dbt deps

dbt-run:
	cd dbt_retail && dbt run --target dev

dbt-test:
	cd dbt_retail && dbt test --target dev

dbt-docs:
	cd dbt_retail && dbt docs generate && dbt docs serve

dbt-compile:
	cd dbt_retail && dbt compile --target dev

# ── Docker ─────────────────────────────────────────────────────────
docker-build:
	docker build -t retail-analytics .

docker-run:
	docker-compose up pipeline

docker-test:
	docker-compose --profile test up test

# ── Cleanup ────────────────────────────────────────────────────────
clean:
	rm -rf data/bronze data/quarantine data/.file_manifest.json
	rm -rf dbt_retail/target dbt_retail/dbt_packages
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
