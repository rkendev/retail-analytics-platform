"""Pipeline runner — orchestrates the full extract → validate → load flow.

This is the local entry point (``python -m src.pipeline.runner``).
In production, Cloud Composer / Airflow DAG calls the same functions
via individual task operators.

Usage::

    python -m src.pipeline.runner --config configs/dev.yaml

"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from src.config import load_config
from src.extractors.api_extractor import ExchangeRatesExtractor
from src.extractors.cdc_extractor import CDCExtractor
from src.extractors.file_extractor import FileExtractor
from src.loaders import GCSLoader
from src.utils import setup_logging
from src.utils.metrics import PipelineMetrics
from src.validators import (
    CustomerContract,
    ExchangeRateContract,
    OrderContract,
    validate_batch,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Summary returned after a pipeline run — useful for assertions in tests."""

    run_id: str
    fact_orders_count: int = 0
    quarantine_count: int = 0
    exchange_rates_count: int = 0
    customer_count: int = 0
    supplier_count: int = 0
    orphaned_customer_count: int = 0
    orphaned_product_count: int = 0


def run_pipeline(
    config_path: str = "configs/dev.yaml",
    target_dataset: str | None = None,
    dry_run: bool = False,
) -> PipelineResult:
    """Execute the full pipeline.

    Parameters
    ----------
    config_path : str
        Path to YAML config file.
    target_dataset : str | None
        Override BigQuery dataset (for integration tests).
    dry_run : bool
        If True, extract and validate but skip loading.
    """
    config = load_config(config_path)
    setup_logging(config.pipeline.log_level)

    metrics = PipelineMetrics()
    run_id = metrics.run_id
    logger.info("🚀 Pipeline run started: %s", run_id)

    gcs = GCSLoader(config, run_id, local_mode=True)
    result = PipelineResult(run_id=run_id)

    try:
        # ── 1. Extract exchange rates ──────────────────────────────
        logger.info("── Extracting exchange rates ──")
        try:
            fx_extractor = ExchangeRatesExtractor(config, run_id)
            fx_raw = fx_extractor.extract()
        except Exception:
            logger.warning("Exchange rates extraction failed — using empty set")
            fx_raw = []

        if fx_raw:
            fx_valid, fx_quarantined = validate_batch(fx_raw, ExchangeRateContract, run_id)
            gcs.load_bronze(fx_valid, "exchange_rates")
            gcs.load_quarantine(fx_quarantined, "exchange_rates")
            result.exchange_rates_count = len(fx_valid)
            metrics.records_quarantined += len(fx_quarantined)

        # ── 2. Extract CDC orders ──────────────────────────────────
        logger.info("── Extracting CDC orders ──")
        cdc = CDCExtractor(config, run_id)
        orders_raw = cdc.extract()
        metrics.records_extracted += len(orders_raw)

        orders_valid, orders_quarantined = validate_batch(orders_raw, OrderContract, run_id)
        gcs.load_bronze(orders_valid, "orders_cdc")
        gcs.load_quarantine(orders_quarantined, "orders_cdc")

        result.fact_orders_count = len(orders_valid)
        result.quarantine_count += len(orders_quarantined)
        metrics.records_validated += len(orders_valid)
        metrics.records_quarantined += len(orders_quarantined)

        # ── 3. Extract customer dimension from CDC orders ──────────
        logger.info("── Extracting customer dimension ──")
        customers_raw = cdc.extract_customers(orders_raw)
        customers_valid, customers_quarantined = validate_batch(
            customers_raw, CustomerContract, run_id
        )
        gcs.load_bronze(customers_valid, "customers")
        gcs.load_quarantine(customers_quarantined, "customers")
        result.customer_count = len(customers_valid)

        # ── 4. Extract supplier catalog files ──────────────────────
        logger.info("── Extracting supplier catalog ──")
        file_ext = FileExtractor(config, run_id, local_dir="data/supplier")
        supplier_raw = file_ext.extract()
        if supplier_raw:
            from src.validators import SupplierCatalogContract

            sup_valid, sup_quarantined = validate_batch(
                supplier_raw, SupplierCatalogContract, run_id
            )
            gcs.load_bronze(sup_valid, "supplier_catalog")
            gcs.load_quarantine(sup_quarantined, "supplier_catalog")
            result.supplier_count = len(sup_valid)

        # ── 5. Summary ────────────────────────────────────────────
        metrics.finish("SUCCESS")
        logger.info(
            "✅ Pipeline run complete: %s | Orders: %d | Quarantined: %d | FX rates: %d | Customers: %d",
            run_id,
            result.fact_orders_count,
            result.quarantine_count,
            result.exchange_rates_count,
            result.customer_count,
        )

    except Exception:
        metrics.finish("FAILED")
        logger.exception("💥 Pipeline run failed: %s", run_id)
        raise

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Retail Analytics Pipeline Runner")
    parser.add_argument(
        "--config",
        default="configs/dev.yaml",
        help="Path to YAML config file (default: configs/dev.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate only — skip loading",
    )
    args = parser.parse_args()

    try:
        result = run_pipeline(config_path=args.config, dry_run=args.dry_run)
        logger.info("Pipeline result: %s", result)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
