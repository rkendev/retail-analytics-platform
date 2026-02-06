#!/usr/bin/env bash
# scripts/setup_airflow.sh
#
# Sets up the Airflow local development environment for retail-analytics-platform.
#
# Usage:
#   chmod +x scripts/setup_airflow.sh
#   ./scripts/setup_airflow.sh
#
set -euo pipefail

echo "🔧 Setting up Airflow local environment..."

# 1. Create required directories
echo "  📁 Creating directories..."
mkdir -p logs secrets data

# 2. Set AIRFLOW_UID in .env (required for Docker volume permissions)
if [ ! -f .env ]; then
    echo "  📝 Creating .env from .env.airflow template..."
    if [ -f .env.airflow ]; then
        cp .env.airflow .env
        # Replace UID with current user's UID
        sed -i "s/AIRFLOW_UID=1000/AIRFLOW_UID=$(id -u)/" .env
        echo "  ✅ .env created — edit GCP_PROJECT and EXCHANGE_RATES_API_KEY"
    else
        echo "AIRFLOW_UID=$(id -u)" > .env
        echo "GCP_PROJECT=nifty-quanta-486115-d6" >> .env
        echo "  ✅ .env created with defaults"
    fi
else
    echo "  ⏭️  .env already exists — skipping"
fi

# 3. Add Makefile targets if not already present
if ! grep -q "airflow-init" Makefile 2>/dev/null; then
    echo "  📝 Adding Airflow targets to Makefile..."
    cat >> Makefile << 'MAKEFILE_ADDITIONS'

# ── Airflow (Local Docker Compose) ──────────────────────────────────
airflow-init:
	docker compose -f docker-compose-airflow.yml up airflow-init

airflow-up:
	docker compose -f docker-compose-airflow.yml up -d
	@echo ""
	@echo "✅ Airflow is starting..."
	@echo "   UI: http://localhost:8080"
	@echo "   Login: airflow / airflow"
	@echo ""
	@echo "   Wait ~30s for services to be healthy, then:"
	@echo "   1. Unpause the 'retail_analytics_daily' DAG"
	@echo "   2. Trigger a manual run (play button)"
	@echo ""

airflow-down:
	docker compose -f docker-compose-airflow.yml down

airflow-reset:
	docker compose -f docker-compose-airflow.yml down -v
	@echo "✅ Airflow volumes removed — run 'make airflow-init' to start fresh"

airflow-logs:
	docker compose -f docker-compose-airflow.yml logs -f airflow-scheduler

airflow-shell:
	docker compose -f docker-compose-airflow.yml exec airflow-scheduler bash
MAKEFILE_ADDITIONS
    echo "  ✅ Makefile targets added: airflow-init, airflow-up, airflow-down, airflow-reset, airflow-logs, airflow-shell"
else
    echo "  ⏭️  Airflow Makefile targets already present — skipping"
fi

# 4. Add secrets/ and logs/ to .gitignore if not already there
for pattern in "secrets/" "logs/" ".env"; do
    if ! grep -q "^${pattern}$" .gitignore 2>/dev/null; then
        echo "${pattern}" >> .gitignore
        echo "  📝 Added '${pattern}' to .gitignore"
    fi
done

# 5. Remind about GCP credentials
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  ✅ Airflow setup complete!                                  ║"
echo "╠═══════════════════════════════════════════════════════════════╣"
echo "║                                                             ║"
echo "║  Before starting, place your GCP service account key at:    ║"
echo "║    secrets/gcp-key.json                                     ║"
echo "║                                                             ║"
echo "║  Or use Application Default Credentials:                    ║"
echo "║    gcloud auth application-default login                    ║"
echo "║    cp ~/.config/gcloud/application_default_credentials.json ║"
echo "║       secrets/gcp-key.json                                  ║"
echo "║                                                             ║"
echo "║  Then run:                                                  ║"
echo "║    make airflow-init    # Initialize DB + create admin      ║"
echo "║    make airflow-up      # Start webserver + scheduler       ║"
echo "║                                                             ║"
echo "║  Open: http://localhost:8080  (airflow / airflow)           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
