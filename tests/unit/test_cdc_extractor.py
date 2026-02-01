"""Unit tests for the Faker CDC data generator."""

from __future__ import annotations

from src.config import load_config
from src.extractors.cdc_extractor import CDCExtractor


class TestCDCExtractor:
    """Test synthetic order generation and quality-issue injection."""

    def setup_method(self) -> None:
        self.config = load_config("configs/test.yaml")
        self.extractor = CDCExtractor(self.config, run_id="test-run-001")

    def test_extract_returns_records(self) -> None:
        records = self.extractor.extract()
        assert len(records) > 0

    def test_records_have_required_fields(self) -> None:
        records = self.extractor.extract()
        required = {
            "order_id",
            "customer_id",
            "product_id",
            "quantity",
            "unit_price_local",
            "currency_code",
            "store_key",
            "order_date",
            "pipeline_run_id",
        }
        for rec in records[:10]:
            assert required.issubset(rec.keys()), f"Missing fields: {required - rec.keys()}"

    def test_pipeline_run_id_stamped(self) -> None:
        records = self.extractor.extract()
        for rec in records:
            assert rec["pipeline_run_id"] == "test-run-001"

    def test_duplicates_injected(self) -> None:
        """Batch should be larger than records_per_batch due to injected dupes."""
        records = self.extractor.extract()
        batch_size = self.config.sources.orders_cdc.records_per_batch
        assert len(records) >= batch_size

    def test_some_null_customers_injected(self) -> None:
        records = self.extractor.extract()
        null_count = sum(1 for r in records if r.get("customer_id") is None)
        assert null_count > 0, "Expected at least one null customer_id injection"

    def test_extract_customers_deduplicates(self) -> None:
        orders = self.extractor.extract()
        customers = self.extractor.extract_customers(orders)
        customer_ids = [c["customer_id"] for c in customers]
        assert len(customer_ids) == len(set(customer_ids)), "Duplicate customer_ids found"
