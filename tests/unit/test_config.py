"""Unit tests for YAML config loading and validation."""

from __future__ import annotations

import pytest

from src.config import AppConfig, load_config


class TestConfigLoader:
    """Test that YAML configs load and validate correctly."""

    def test_load_dev_config(self) -> None:
        config = load_config("configs/dev.yaml")
        assert isinstance(config, AppConfig)
        assert config.gcp.project_id == "retail-analytics-dev"
        assert config.sources.orders_cdc.records_per_batch == 100

    def test_load_test_config(self) -> None:
        config = load_config("configs/test.yaml")
        assert config.gcp.project_id == "retail-analytics-test"
        assert config.pipeline.max_retries == 0

    def test_load_prod_config(self) -> None:
        config = load_config("configs/prod.yaml")
        assert config.gcp.project_id == "retail-analytics-prod"
        assert config.sources.orders_cdc.records_per_batch == 1000

    def test_missing_config_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_config("configs/nonexistent.yaml")

    def test_quality_thresholds(self) -> None:
        config = load_config("configs/dev.yaml")
        assert config.quality.null_rate_threshold == 0.05
        assert config.quality.min_daily_orders == 10
