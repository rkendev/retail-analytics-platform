"""Unit tests for Pydantic data contracts and batch validation.

These tests run without any external dependencies (no GCP, no network).
They verify:
  • Valid records pass validation
  • Each business rule rejects bad data correctly
  • The batch validator splits valid/quarantined correctly
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.validators import ExchangeRateContract, OrderContract, validate_batch


# ---------------------------------------------------------------------------
# OrderContract tests
# ---------------------------------------------------------------------------
class TestOrderContract:
    """Test the OrderContract Pydantic model."""

    VALID_ORDER = {
        "order_id": 1,
        "customer_id": 100,
        "product_id": 50,
        "quantity": 2,
        "unit_price_local": 29.99,
        "currency_code": "USD",
        "order_date": "2026-01-15T10:00:00",
        "store_key": "S-101",
    }

    def test_valid_order_passes(self) -> None:
        validated = OrderContract(**self.VALID_ORDER)
        assert validated.order_id == 1
        assert validated.currency_code == "USD"

    def test_negative_order_id_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "order_id": -1}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_zero_quantity_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "quantity": 0}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_negative_price_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "unit_price_local": -5.00}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_invalid_currency_code_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "currency_code": "us"}  # lowercase
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_four_letter_currency_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "currency_code": "USDD"}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_future_date_rejected(self) -> None:
        bad = {**self.VALID_ORDER, "order_date": "2099-01-15T10:00:00"}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_missing_required_field_rejected(self) -> None:
        bad = {k: v for k, v in self.VALID_ORDER.items() if k != "store_key"}
        with pytest.raises(ValidationError):
            OrderContract(**bad)

    def test_extra_fields_ignored(self) -> None:
        """Extra fields from source should not break validation (extra='ignore')."""
        extended = {**self.VALID_ORDER, "unknown_field": "surprise"}
        validated = OrderContract(**extended)
        assert validated.order_id == 1
        assert not hasattr(validated, "unknown_field")


# ---------------------------------------------------------------------------
# ExchangeRateContract tests
# ---------------------------------------------------------------------------
class TestExchangeRateContract:
    """Test the ExchangeRateContract Pydantic model."""

    def test_valid_rate_passes(self) -> None:
        rate = ExchangeRateContract(
            currency_code="EUR",
            rate_to_usd=1.08,
            rate_date="2026-01-15",
        )
        assert rate.rate_to_usd == 1.08

    def test_zero_rate_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExchangeRateContract(
                currency_code="EUR",
                rate_to_usd=0.0,
                rate_date="2026-01-15",
            )


# ---------------------------------------------------------------------------
# validate_batch tests
# ---------------------------------------------------------------------------
class TestValidateBatch:
    """Test the generic batch validation function."""

    def test_splits_valid_and_quarantined(self) -> None:
        good = {
            "order_id": 1,
            "customer_id": 1,
            "product_id": 1,
            "quantity": 1,
            "unit_price_local": 10.0,
            "currency_code": "USD",
            "order_date": "2026-01-15T10:00:00",
            "store_key": "S-101",
        }
        bad = {
            "order_id": -1,
            "customer_id": None,
            "product_id": 1,
            "quantity": 1,
            "unit_price_local": 10.0,
            "currency_code": "USD",
            "order_date": "2026-01-15T10:00:00",
            "store_key": "S-101",
        }
        valid, quarantined = validate_batch([good, bad], OrderContract, "run-001")
        assert len(valid) == 1
        assert len(quarantined) == 1

    def test_all_valid(self) -> None:
        records = [
            {
                "order_id": i,
                "customer_id": i,
                "product_id": i,
                "quantity": 1,
                "unit_price_local": 10.0,
                "currency_code": "USD",
                "order_date": "2026-01-15T10:00:00",
                "store_key": "S-101",
            }
            for i in range(1, 6)
        ]
        valid, quarantined = validate_batch(records, OrderContract, "run-002")
        assert len(valid) == 5
        assert len(quarantined) == 0

    def test_all_quarantined(self) -> None:
        bad_records = [{"order_id": -i, "customer_id": None} for i in range(1, 4)]
        valid, quarantined = validate_batch(bad_records, OrderContract, "run-003")
        assert len(valid) == 0
        assert len(quarantined) == 3

    def test_quarantined_records_contain_error_details(self) -> None:
        bad = {"order_id": -1}
        _, quarantined = validate_batch([bad], OrderContract, "run-004")
        assert len(quarantined) == 1
        assert "errors" in quarantined[0]
        assert quarantined[0]["pipeline_run_id"] == "run-004"

    def test_empty_batch(self) -> None:
        valid, quarantined = validate_batch([], OrderContract, "run-005")
        assert valid == []
        assert quarantined == []
