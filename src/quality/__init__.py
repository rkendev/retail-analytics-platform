"""Data quality gates — circuit breakers between staging and marts.

These SQL assertions run *after* staging models are refreshed but
*before* mart models build.  If any CRITICAL check fails, the pipeline
halts immediately to prevent bad data from reaching the gold layer.

Usage in the pipeline runner::

    gate = QualityGate(config, run_id)
    gate.run_all()  # raises QualityGateError on CRITICAL failures

Usage in Airflow::

    run_quality_gates = PythonOperator(
        task_id="run_data_quality_gates",
        python_callable=gate.run_all,
    )
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.config import AppConfig

logger = logging.getLogger(__name__)


class QualityGateError(Exception):
    """Raised when a CRITICAL quality check fails."""

    def __init__(self, failed_checks: list[str]) -> None:
        self.failed_checks = failed_checks
        super().__init__(f"CRITICAL quality gates failed: {', '.join(failed_checks)}")


@dataclass
class QualityCheck:
    """A single quality assertion."""

    name: str
    sql: str
    assertion: Callable[[dict[str, Any]], bool]
    severity: str = "CRITICAL"  # CRITICAL | WARNING


class QualityGate:
    """Run a suite of quality checks and halt on critical failures."""

    def __init__(self, config: AppConfig, run_id: str) -> None:
        self.config = config
        self.run_id = run_id
        self.project = config.gcp.project_id
        self.staging = config.bigquery.staging_dataset
        self._client = None

    @property
    def client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project)
        return self._client

    @property
    def checks(self) -> list[QualityCheck]:
        """Define quality checks.  Easily extensible."""
        return [
            QualityCheck(
                name="orders_not_empty",
                sql=f"""
                    SELECT COUNT(*) AS cnt
                    FROM `{self.project}.{self.staging}.stg_orders`
                    WHERE DATE(order_date) = CURRENT_DATE()
                """,
                assertion=lambda r: r["cnt"] > 0,
                severity="CRITICAL",
            ),
            QualityCheck(
                name="null_customer_rate_below_threshold",
                sql=f"""
                    SELECT SAFE_DIVIDE(
                        COUNTIF(customer_id IS NULL), COUNT(*)
                    ) AS null_rate
                    FROM `{self.project}.{self.staging}.stg_orders`
                    WHERE DATE(order_date) = CURRENT_DATE()
                """,
                assertion=lambda r: (r["null_rate"] or 0) < self.config.quality.null_rate_threshold,
                severity="CRITICAL",
            ),
            QualityCheck(
                name="revenue_sanity_check",
                sql=f"""
                    SELECT SUM(unit_price_local * quantity) AS total
                    FROM `{self.project}.{self.staging}.stg_orders`
                    WHERE DATE(order_date) = CURRENT_DATE()
                """,
                assertion=lambda r: (r["total"] or 0) > 0,
                severity="CRITICAL",
            ),
            QualityCheck(
                name="duplicate_order_ids",
                sql=f"""
                    SELECT COUNT(*) AS dupe_count
                    FROM (
                        SELECT order_id, COUNT(*) AS n
                        FROM `{self.project}.{self.staging}.stg_orders`
                        WHERE DATE(order_date) = CURRENT_DATE()
                        GROUP BY order_id
                        HAVING n > 1
                    )
                """,
                assertion=lambda r: r["dupe_count"] == 0,
                severity="WARNING",
            ),
        ]

    def _run_check(self, check: QualityCheck) -> tuple[bool, dict[str, Any]]:
        """Execute a single check and return (passed, result_row)."""
        try:
            result = self.client.query(check.sql).result()
            row = dict(next(iter(result)))
            passed = check.assertion(row)
            return passed, row
        except Exception:
            logger.exception("Quality check '%s' errored", check.name)
            return False, {}

    def run_all(self) -> dict[str, Any]:
        """Run all checks.  Raises ``QualityGateError`` if any CRITICAL fails."""
        results: dict[str, Any] = {}
        critical_failures: list[str] = []

        for check in self.checks:
            passed, row = self._run_check(check)
            status = "PASS" if passed else "FAIL"
            results[check.name] = {"status": status, "result": row, "severity": check.severity}

            if passed:
                logger.info("✅ %s: PASS %s", check.name, row)
            else:
                logger.warning("❌ %s: FAIL %s [%s]", check.name, row, check.severity)
                if check.severity == "CRITICAL":
                    critical_failures.append(check.name)

        if critical_failures:
            raise QualityGateError(critical_failures)

        logger.info(
            "All quality gates passed (%d checks)",
            len(self.checks),
            extra={"pipeline_run_id": self.run_id},
        )
        return results


# ---------------------------------------------------------------------------
# Local / offline quality checks (no BigQuery required)
# ---------------------------------------------------------------------------
def check_local_bronze_counts(data_dir: str = "data/bronze") -> dict[str, int]:
    """Quick local check: count files per source in bronze directory."""
    from pathlib import Path

    root = Path(data_dir)
    counts: dict[str, int] = {}
    if root.exists():
        for source_dir in root.iterdir():
            if source_dir.is_dir():
                file_count = sum(1 for _ in source_dir.rglob("*") if _.is_file())
                counts[source_dir.name] = file_count
    return counts
