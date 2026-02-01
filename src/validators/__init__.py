"""Pydantic data contracts for schema validation with quarantine routing.

Each source has a dedicated model that acts as the *data contract*.
Records that pass validation proceed to bronze; records that fail are
routed to the quarantine bucket with full error context.

Design decisions
----------------
* ``model_config = ConfigDict(extra="ignore")`` — gracefully skip unknown
  fields so upstream schema additions don't break the pipeline.
* The ``validate_batch`` function returns a ``(valid, quarantined)`` tuple
  so callers never have to catch validation errors themselves.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Order contract
# ---------------------------------------------------------------------------
class OrderContract(BaseModel):
    """Validates a single order/CDC record."""

    model_config = ConfigDict(extra="ignore")

    order_id: int = Field(gt=0)
    customer_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price_local: float = Field(gt=0)
    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    order_date: datetime
    store_key: str

    @field_validator("order_date")
    @classmethod
    def not_future_date(cls, v: datetime) -> datetime:
        if v.replace(tzinfo=None) > datetime.now(UTC).replace(tzinfo=None):
            raise ValueError("Order date cannot be in the future")
        return v


# ---------------------------------------------------------------------------
# Exchange rate contract
# ---------------------------------------------------------------------------
class ExchangeRateContract(BaseModel):
    """Validates a single exchange-rate record."""

    model_config = ConfigDict(extra="ignore")

    currency_code: str = Field(pattern=r"^[A-Z]{3}$")
    rate_to_usd: float = Field(gt=0)
    base_currency: str = "USD"
    rate_date: str  # ISO date string


# ---------------------------------------------------------------------------
# Supplier catalog contract
# ---------------------------------------------------------------------------
class SupplierCatalogContract(BaseModel):
    """Validates a single supplier catalog record."""

    model_config = ConfigDict(extra="ignore")

    product_id: int = Field(gt=0)
    product_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subcategory: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    supplier_id: int = Field(gt=0)
    unit_cost: float = Field(ge=0)


# ---------------------------------------------------------------------------
# Customer contract (for CDC-generated companion records)
# ---------------------------------------------------------------------------
class CustomerContract(BaseModel):
    """Validates a single customer dimension record."""

    model_config = ConfigDict(extra="ignore")

    customer_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    email: str
    city: str
    country: str = Field(pattern=r"^[A-Z]{2}$")
    signup_date: str
    customer_segment: str


# ---------------------------------------------------------------------------
# Generic batch validator
# ---------------------------------------------------------------------------
def validate_batch(
    records: list[dict],
    contract_cls: type[BaseModel],
    run_id: str,
) -> tuple[list[dict], list[dict]]:
    """Validate a batch of records against a Pydantic contract.

    Parameters
    ----------
    records : list[dict]
        Raw records to validate.
    contract_cls : type[BaseModel]
        The Pydantic model to validate against.
    run_id : str
        Pipeline run ID for audit trail.

    Returns
    -------
    tuple[list[dict], list[dict]]
        ``(valid_records, quarantined_records)``
    """
    valid: list[dict] = []
    quarantined: list[dict] = []

    for record in records:
        try:
            validated = contract_cls(**record)
            valid.append({**validated.model_dump(), "pipeline_run_id": run_id})
        except ValidationError as exc:
            quarantined.append(
                {
                    "raw_record": record,
                    "errors": exc.json(),
                    "contract": contract_cls.__name__,
                    "pipeline_run_id": run_id,
                    "quarantined_at": datetime.now(UTC).isoformat(),
                }
            )

    logger.info(
        "Validation complete [%s]: %d valid, %d quarantined (of %d total)",
        contract_cls.__name__,
        len(valid),
        len(quarantined),
        len(records),
        extra={
            "pipeline_run_id": run_id,
            "record_count": len(records),
        },
    )
    return valid, quarantined
