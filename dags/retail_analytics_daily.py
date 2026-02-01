"""Airflow DAG: retail_analytics_daily

Orchestrates the full retail analytics pipeline:
  1. Check API availability
  2. Extract from all three sources (parallel)
  3. Validate and load to bronze
  4. Run dbt staging models
  5. Run quality gates (circuit breaker)
  6. Run dbt mart models
  7. Notify on completion

Designed for Cloud Composer (managed Airflow 2.x) but works with
any Airflow 2.8+ installation.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# ── DAG default args ──────────────────────────────────────────────
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=1),
}


# ── Task callables ────────────────────────────────────────────────
def _check_api_availability(**context: object) -> bool:
    """Health check for Open Exchange Rates API."""
    import requests

    try:
        resp = requests.get(
            "https://openexchangerates.org/api/latest.json",
            params={"app_id": "test"},
            timeout=10,
        )
        return resp.status_code in (200, 401)  # 401 = key issue, but API is up
    except requests.RequestException:
        return False


def _run_extraction(**context: object) -> dict:
    """Run the full extraction + validation + bronze load."""
    from src.pipeline import run_pipeline

    result = run_pipeline(config_path="configs/prod.yaml")
    return {
        "run_id": result.run_id,
        "orders": result.fact_orders_count,
        "quarantined": result.quarantine_count,
    }


def _run_quality_gates(**context: object) -> None:
    """Execute quality gate assertions — halts pipeline on CRITICAL failure."""
    from src.config import load_config
    from src.quality import QualityGate

    config = load_config("configs/prod.yaml")
    ti = context["ti"]
    extraction_result = ti.xcom_pull(task_ids="extract_and_load")
    run_id = extraction_result.get("run_id", "unknown")
    gate = QualityGate(config, run_id)
    gate.run_all()


# ── DAG definition ────────────────────────────────────────────────
with DAG(
    dag_id="retail_analytics_daily",
    default_args=default_args,
    description="Daily retail analytics pipeline: extract → validate → transform → serve",
    schedule="0 6 * * *",  # 6 AM UTC daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["retail", "analytics", "production"],
    doc_md=__doc__,
) as dag:
    # 1. Health check
    check_api = PythonOperator(
        task_id="check_api_availability",
        python_callable=_check_api_availability,
    )

    # 2. Extract + validate + load to bronze
    extract_and_load = PythonOperator(
        task_id="extract_and_load",
        python_callable=_run_extraction,
    )

    # 3. dbt staging
    dbt_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command="cd /app/dbt_retail && dbt run --select staging --target prod",
    )

    # 4. Quality gates (circuit breaker)
    quality_gates = PythonOperator(
        task_id="run_quality_gates",
        python_callable=_run_quality_gates,
    )

    # 5. dbt marts
    dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="cd /app/dbt_retail && dbt run --select marts --target prod",
    )

    # 6. dbt tests
    dbt_tests = BashOperator(
        task_id="dbt_test",
        bash_command="cd /app/dbt_retail && dbt test --target prod",
    )

    # 7. Notification (placeholder)
    notify = BashOperator(
        task_id="notify_completion",
        bash_command='echo "Pipeline complete: $(date)"',
        trigger_rule="all_done",  # Runs even if upstream failed (for alerting)
    )

    # ── Dependencies ──────────────────────────────────────────────
    (
        check_api
        >> extract_and_load
        >> dbt_staging
        >> quality_gates
        >> dbt_marts
        >> dbt_tests
        >> notify
    )
