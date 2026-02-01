"""End-to-end integration tests.

These tests run the full pipeline locally (no GCP required) and validate
that bronze data is produced correctly.

Requires: configs/test.yaml

Run with:
    pytest tests/integration/ -v -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline import PipelineResult, run_pipeline


@pytest.fixture(scope="module")
def pipeline_result() -> PipelineResult:
    """Run the full local pipeline once for all integration tests."""
    return run_pipeline(config_path="configs/test.yaml", dry_run=False)


@pytest.mark.integration
class TestPipelineE2E:
    """End-to-end pipeline integration tests."""

    def test_pipeline_produces_orders(self, pipeline_result: PipelineResult) -> None:
        assert pipeline_result.fact_orders_count > 0

    def test_quarantine_captured_bad_records(self, pipeline_result: PipelineResult) -> None:
        # We inject known-bad data via null_injection_pct
        assert pipeline_result.quarantine_count > 0

    def test_customers_generated(self, pipeline_result: PipelineResult) -> None:
        assert pipeline_result.customer_count > 0

    def test_bronze_files_created(self, pipeline_result: PipelineResult) -> None:
        bronze = Path("data/bronze")
        assert bronze.exists()
        assert any(bronze.rglob("*.parquet")) or any(bronze.rglob("*.jsonl"))

    def test_quarantine_files_created(self, pipeline_result: PipelineResult) -> None:
        quarantine = Path("data/quarantine")
        assert quarantine.exists()
        assert any(quarantine.rglob("*.jsonl"))

    def test_run_id_is_uuid(self, pipeline_result: PipelineResult) -> None:
        assert len(pipeline_result.run_id) == 36
