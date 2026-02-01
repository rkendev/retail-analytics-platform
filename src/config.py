"""Typed configuration loader.

Reads YAML configs and exposes them as validated Pydantic models.
Supports environment variable overrides for secrets.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config schema
# ---------------------------------------------------------------------------
class GCPConfig(BaseModel):
    project_id: str
    region: str = "us-central1"


class StorageConfig(BaseModel):
    bronze_bucket: str
    quarantine_bucket: str


class BigQueryConfig(BaseModel):
    staging_dataset: str
    marts_dataset: str
    metadata_dataset: str


class ExchangeRatesSourceConfig(BaseModel):
    api_url: str
    api_key_env: str = "EXCHANGE_RATES_API_KEY"
    schedule: str = "daily"

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "")
        if not key:
            raise OSError(f"Missing environment variable: {self.api_key_env}")
        return key


class OrdersCDCSourceConfig(BaseModel):
    records_per_batch: int = 1000
    late_arrival_pct: float = 0.05
    null_injection_pct: float = 0.02
    duplicate_pct: float = 0.03
    schedule: str = "hourly"


class SupplierCatalogSourceConfig(BaseModel):
    file_prefix: str = "supplier_catalog_"
    expected_columns: list[str] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    exchange_rates: ExchangeRatesSourceConfig
    orders_cdc: OrdersCDCSourceConfig
    supplier_catalog: SupplierCatalogSourceConfig


class QualityConfig(BaseModel):
    null_rate_threshold: float = 0.01
    min_daily_orders: int = 100
    max_revenue_deviation_pct: float = 0.50
    quarantine_alert_threshold: int = 50


class PipelineConfig(BaseModel):
    max_retries: int = 3
    retry_delay_seconds: int = 300
    retry_exponential_backoff: bool = True
    log_level: str = "INFO"


class AppConfig(BaseModel):
    gcp: GCPConfig
    storage: StorageConfig
    bigquery: BigQueryConfig
    sources: SourcesConfig
    quality: QualityConfig
    pipeline: PipelineConfig


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate a YAML config file into an AppConfig model."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)
