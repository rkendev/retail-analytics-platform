"""Load local bronze data into BigQuery raw tables.

This script bridges the local pipeline output (Parquet files in data/bronze/)
with BigQuery so dbt can transform the data into the star schema.

Usage:
    python scripts/load_to_bigquery.py --project <GCP_PROJECT_ID>
    python scripts/load_to_bigquery.py --project retail-analytics-dev-12345

What it does:
    1. Reads Parquet files from data/bronze/
    2. Creates raw_* tables in the staging_dev dataset
    3. Loads the data via BigQuery load jobs (efficient, not streaming)

Prerequisites:
    - GCP project set up (run scripts/gcp_setup.sh first)
    - Application default credentials configured
    - pip install google-cloud-bigquery pyarrow
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.cloud import bigquery

# ── Table schemas ────────────────────────────────────────────────────────────
# Explicit schemas ensure clean table creation.
# These match what dbt staging models expect.

SCHEMAS = {
    "raw_orders": [
        bigquery.SchemaField("order_id", "INTEGER"),
        bigquery.SchemaField("customer_id", "INTEGER"),
        bigquery.SchemaField("product_id", "INTEGER"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("subcategory", "STRING"),
        bigquery.SchemaField("quantity", "INTEGER"),
        bigquery.SchemaField("unit_price_local", "FLOAT"),
        bigquery.SchemaField("currency_code", "STRING"),
        bigquery.SchemaField("store_key", "STRING"),
        bigquery.SchemaField("order_date", "TIMESTAMP"),
        bigquery.SchemaField("updated_at", "TIMESTAMP"),
        bigquery.SchemaField("cdc_operation", "STRING"),
        bigquery.SchemaField("pipeline_run_id", "STRING"),
    ],
    "raw_customers": [
        bigquery.SchemaField("customer_id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("email", "STRING"),
        bigquery.SchemaField("city", "STRING"),
        bigquery.SchemaField("country", "STRING"),
        bigquery.SchemaField("signup_date", "STRING"),
        bigquery.SchemaField("customer_segment", "STRING"),
        bigquery.SchemaField("pipeline_run_id", "STRING"),
    ],
    "raw_exchange_rates": [
        bigquery.SchemaField("currency_code", "STRING"),
        bigquery.SchemaField("rate_to_usd", "FLOAT"),
        bigquery.SchemaField("base_currency", "STRING"),
        bigquery.SchemaField("rate_date", "STRING"),
        bigquery.SchemaField("fetched_at", "STRING"),
        bigquery.SchemaField("pipeline_run_id", "STRING"),
    ],
    "raw_supplier_catalog": [
        bigquery.SchemaField("product_id", "INTEGER"),
        bigquery.SchemaField("product_name", "STRING"),
        bigquery.SchemaField("category", "STRING"),
        bigquery.SchemaField("subcategory", "STRING"),
        bigquery.SchemaField("brand", "STRING"),
        bigquery.SchemaField("supplier_id", "INTEGER"),
        bigquery.SchemaField("unit_cost", "FLOAT"),
        bigquery.SchemaField("source_file", "STRING"),
        bigquery.SchemaField("pipeline_run_id", "STRING"),
    ],
}

# Map bronze directory names → BigQuery table names
SOURCE_TO_TABLE = {
    "orders_cdc": "raw_orders",
    "customers": "raw_customers",
    "exchange_rates": "raw_exchange_rates",
    "supplier_catalog": "raw_supplier_catalog",
}


def find_parquet_files(bronze_dir: Path) -> dict[str, list[Path]]:
    """Discover Parquet files grouped by source."""
    results: dict[str, list[Path]] = {}
    if not bronze_dir.exists():
        print(f"❌ Bronze directory not found: {bronze_dir}")
        print("   Run 'make run-local' first to generate data.")
        sys.exit(1)

    for source_dir in sorted(bronze_dir.iterdir()):
        if source_dir.is_dir():
            parquet_files = sorted(source_dir.rglob("*.parquet"))
            if parquet_files:
                results[source_dir.name] = parquet_files
    return results


def load_table(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    table_name: str,
    parquet_files: list[Path],
    schema: list[bigquery.SchemaField],
) -> int:
    """Load Parquet files into a BigQuery table."""
    table_ref = f"{project_id}.{dataset}.{table_name}"

    # Create or replace table with explicit schema
    table = bigquery.Table(table_ref, schema=schema)
    client.delete_table(table_ref, not_found_ok=True)
    client.create_table(table)
    print(f"   📋 Created table: {table_ref}")

    total_rows = 0
    for pq_file in parquet_files:
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        with open(pq_file, "rb") as f:
            job = client.load_table_from_file(f, table_ref, job_config=job_config)

        job.result()  # Wait for completion
        rows = job.output_rows or 0
        total_rows += rows
        print(f"   📦 Loaded {rows} rows from {pq_file.name}")

    return total_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Load local bronze data into BigQuery")
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID (e.g., retail-analytics-dev-12345)",
    )
    parser.add_argument(
        "--dataset",
        default="staging_dev",
        help="BigQuery dataset name (default: staging_dev)",
    )
    parser.add_argument(
        "--bronze-dir",
        default="data/bronze",
        help="Path to local bronze directory (default: data/bronze)",
    )
    args = parser.parse_args()

    bronze_dir = Path(args.bronze_dir)
    print("🚀 Loading bronze data into BigQuery")
    print(f"   Project:  {args.project}")
    print(f"   Dataset:  {args.dataset}")
    print(f"   Source:   {bronze_dir}")
    print()

    # Discover files
    source_files = find_parquet_files(bronze_dir)
    if not source_files:
        print("❌ No Parquet files found in bronze directory.")
        print("   Run 'make run-local' first to generate data.")
        sys.exit(1)

    print(f"📂 Found {len(source_files)} sources:")
    for source, files in source_files.items():
        print(f"   {source}: {len(files)} file(s)")
    print()

    # Load each source
    client = bigquery.Client(project=args.project)
    grand_total = 0

    for source_name, files in source_files.items():
        table_name = SOURCE_TO_TABLE.get(source_name)
        if table_name is None:
            print(f"   ⏭️  Skipping unknown source: {source_name}")
            continue

        schema = SCHEMAS.get(table_name)
        if schema is None:
            print(f"   ⏭️  No schema defined for: {table_name}")
            continue

        print(f"── Loading {source_name} → {table_name} ──")
        rows = load_table(
            client=client,
            project_id=args.project,
            dataset=args.dataset,
            table_name=table_name,
            parquet_files=files,
            schema=schema,
        )
        grand_total += rows
        print(f"   ✅ {table_name}: {rows} rows loaded")
        print()

    # Summary
    print("═══════════════════════════════════════════════════════════════")
    print(f"✅ All data loaded! Total rows: {grand_total}")
    print()
    print("Next steps:")
    print("   cd dbt_retail")
    print("   dbt deps")
    print("   dbt run --target dev")
    print("   dbt test --target dev")
    print("═══════════════════════════════════════════════════════════════")


if __name__ == "__main__":
    main()
