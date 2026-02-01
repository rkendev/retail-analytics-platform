#!/usr/bin/env bash
# ==============================================================================
# GCP Setup Script for retail-analytics-platform
#
# Prerequisites:
#   1. Google Cloud SDK installed (https://cloud.google.com/sdk/docs/install)
#   2. A GCP project created (free tier or $300 credit)
#   3. Billing enabled on the project
#
# Usage:
#   chmod +x scripts/gcp_setup.sh
#   ./scripts/gcp_setup.sh <YOUR_GCP_PROJECT_ID>
#
# Example:
#   ./scripts/gcp_setup.sh retail-analytics-dev-12345
# ==============================================================================

set -euo pipefail

# ── Validate input ────────────────────────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo "❌ Usage: $0 <GCP_PROJECT_ID>"
    echo "   Example: $0 retail-analytics-dev-12345"
    exit 1
fi

PROJECT_ID="$1"
REGION="us-central1"

echo "🚀 Setting up GCP resources for project: ${PROJECT_ID}"
echo "   Region: ${REGION}"
echo ""

# ── 1. Set project and authenticate ──────────────────────────────────────────
echo "── Step 1: Setting active project ──"
gcloud config set project "${PROJECT_ID}"

echo "── Step 2: Authenticating for application default credentials ──"
echo "   (This opens a browser window — sign in with your Google account)"
gcloud auth application-default login

# ── 2. Enable required APIs ──────────────────────────────────────────────────
echo ""
echo "── Step 3: Enabling required APIs ──"
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
echo "   ✅ APIs enabled"

# ── 3. Create GCS buckets ───────────────────────────────────────────────────
echo ""
echo "── Step 4: Creating GCS buckets ──"

BRONZE_BUCKET="${PROJECT_ID}-bronze"
QUARANTINE_BUCKET="${PROJECT_ID}-quarantine"

# Create bronze bucket (if it doesn't exist)
if gsutil ls -b "gs://${BRONZE_BUCKET}" 2>/dev/null; then
    echo "   ⏭️  Bronze bucket already exists: gs://${BRONZE_BUCKET}"
else
    gsutil mb -l "${REGION}" -p "${PROJECT_ID}" "gs://${BRONZE_BUCKET}"
    echo "   ✅ Created: gs://${BRONZE_BUCKET}"
fi

# Create quarantine bucket
if gsutil ls -b "gs://${QUARANTINE_BUCKET}" 2>/dev/null; then
    echo "   ⏭️  Quarantine bucket already exists: gs://${QUARANTINE_BUCKET}"
else
    gsutil mb -l "${REGION}" -p "${PROJECT_ID}" "gs://${QUARANTINE_BUCKET}"
    echo "   ✅ Created: gs://${QUARANTINE_BUCKET}"
fi

# Enable versioning on bronze (immutable layer)
gsutil versioning set on "gs://${BRONZE_BUCKET}"
echo "   ✅ Object versioning enabled on bronze bucket"

# ── 4. Create BigQuery datasets ─────────────────────────────────────────────
echo ""
echo "── Step 5: Creating BigQuery datasets ──"

for DATASET in staging_dev marts_dev metadata_dev; do
    if bq ls --project_id="${PROJECT_ID}" "${DATASET}" 2>/dev/null; then
        echo "   ⏭️  Dataset already exists: ${DATASET}"
    else
        bq mk --project_id="${PROJECT_ID}" \
               --location="${REGION}" \
               --dataset "${PROJECT_ID}:${DATASET}"
        echo "   ✅ Created dataset: ${DATASET}"
    fi
done

# ── 5. Create metadata tables ───────────────────────────────────────────────
echo ""
echo "── Step 6: Creating metadata tables ──"

# ETL watermarks table
bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false --nouse_cache \
"CREATE TABLE IF NOT EXISTS \`${PROJECT_ID}.metadata_dev.etl_watermarks\` (
    table_name STRING NOT NULL,
    last_loaded_at TIMESTAMP NOT NULL
);"
echo "   ✅ Created: metadata_dev.etl_watermarks"

# Pipeline runs audit table
bq query --project_id="${PROJECT_ID}" --use_legacy_sql=false --nouse_cache \
"CREATE TABLE IF NOT EXISTS \`${PROJECT_ID}.metadata_dev.pipeline_runs\` (
    run_id STRING NOT NULL,
    dag_id STRING,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status STRING,
    records_extracted INT64,
    records_validated INT64,
    records_quarantined INT64,
    records_loaded INT64,
    quality_checks_passed INT64,
    quality_checks_failed INT64,
    duration_seconds FLOAT64
);"
echo "   ✅ Created: metadata_dev.pipeline_runs"

# ── 6. Summary ──────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ GCP setup complete!"
echo ""
echo "   Project:     ${PROJECT_ID}"
echo "   Region:      ${REGION}"
echo "   Buckets:     gs://${BRONZE_BUCKET}"
echo "                gs://${QUARANTINE_BUCKET}"
echo "   Datasets:    staging_dev, marts_dev, metadata_dev"
echo "   Metadata:    etl_watermarks, pipeline_runs"
echo ""
echo "Next steps:"
echo "   1. Update configs/dev.yaml with your project ID:"
echo "      gcp.project_id: \"${PROJECT_ID}\""
echo "      storage.bronze_bucket: \"${BRONZE_BUCKET}\""
echo "      storage.quarantine_bucket: \"${QUARANTINE_BUCKET}\""
echo ""
echo "   2. Load data into BigQuery:"
echo "      python scripts/load_to_bigquery.py --project ${PROJECT_ID}"
echo ""
echo "   3. Run dbt:"
echo "      cd dbt_retail && dbt deps && dbt run --target dev"
echo "═══════════════════════════════════════════════════════════════"
