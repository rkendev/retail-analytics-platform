"""Faker-based CDC simulator for point-of-sale order data.

Generates realistic retail transactions as if read from a PostgreSQL
CDC replication log.  Injects controlled data quality problems —
late arrivals, nulls, duplicates — so the pipeline's validation and
quarantine logic can be demonstrated.

Key design choices
------------------
* ``updated_at`` drives incremental extraction (high-water mark pattern).
* ``cdc_operation`` (I/U/D) simulates insert/update/delete events.
* Quality issues are injected at configurable rates from ``configs/*.yaml``.
"""

from __future__ import annotations

import copy
import logging
import random
from datetime import UTC, datetime, timedelta

from faker import Faker

from src.config import AppConfig
from src.extractors import BaseExtractor

logger = logging.getLogger(__name__)
fake = Faker()
Faker.seed(42)  # reproducible across runs for demos

# ---------- Static lookup data ----------
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "BRL", "INR"]
STORES = [f"S-{i:03d}" for i in range(1, 21)]
CATEGORIES = {
    "Electronics": ["Laptops", "Headphones", "Cables", "Monitors", "Keyboards"],
    "Clothing": ["T-Shirts", "Jeans", "Jackets", "Shoes", "Hats"],
    "Home": ["Furniture", "Lighting", "Kitchen", "Bedding", "Decor"],
    "Grocery": ["Produce", "Dairy", "Snacks", "Beverages", "Frozen"],
}


class CDCExtractor(BaseExtractor):
    """Generate a batch of synthetic POS order records."""

    source_name = "orders_cdc"  # type: ignore[assignment]

    def __init__(self, config: AppConfig, run_id: str) -> None:
        super().__init__(config, run_id)
        self.src_cfg = config.sources.orders_cdc

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------
    def _generate_order(self, order_id: int) -> dict:
        """Create a single clean order record."""
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        order_date = fake.date_time_between(start_date="-30d", end_date="now", tzinfo=UTC)

        return {
            "order_id": order_id,
            "customer_id": random.randint(1, 5000),
            "product_id": random.randint(1, 500),
            "product_name": f"{fake.word().title()} {subcategory}",
            "category": category,
            "subcategory": subcategory,
            "quantity": random.randint(1, 10),
            "unit_price_local": round(random.uniform(5.0, 500.0), 2),
            "currency_code": random.choice(CURRENCIES),
            "store_key": random.choice(STORES),
            "order_date": order_date.isoformat(),
            "updated_at": self._now_utc().isoformat(),
            "cdc_operation": "I",  # insert
        }

    def _generate_customer(self, customer_id: int) -> dict:
        """Companion customer record for the orders."""
        return {
            "customer_id": customer_id,
            "name": fake.name(),
            "email": fake.email(),
            "city": fake.city(),
            "country": fake.country_code(),
            "signup_date": fake.date_between(start_date="-3y", end_date="-1d").isoformat(),
            "customer_segment": random.choice(["Bronze", "Silver", "Gold", "Platinum"]),
        }

    # ------------------------------------------------------------------
    # Quality issue injection
    # ------------------------------------------------------------------
    def _inject_late_arrivals(self, records: list[dict]) -> list[dict]:
        """Push some records' order_date back 2-7 days (simulates late CDC)."""
        n = int(len(records) * self.src_cfg.late_arrival_pct)
        for rec in random.sample(records, min(n, len(records))):
            original = datetime.fromisoformat(rec["order_date"])
            rec["order_date"] = (original - timedelta(days=random.randint(2, 7))).isoformat()
        logger.debug("Injected %d late-arrival records", n)
        return records

    def _inject_nulls(self, records: list[dict]) -> list[dict]:
        """Null out customer_id on a fraction of records."""
        n = int(len(records) * self.src_cfg.null_injection_pct)
        for rec in random.sample(records, min(n, len(records))):
            rec["customer_id"] = None
        logger.debug("Injected %d null-customer records", n)
        return records

    def _inject_duplicates(self, records: list[dict]) -> list[dict]:
        """Duplicate a fraction of records (same order_id, different timestamp)."""
        n = int(len(records) * self.src_cfg.duplicate_pct)
        dupes = []
        for rec in random.sample(records, min(n, len(records))):
            dupe = copy.deepcopy(rec)
            dupe["updated_at"] = self._now_utc().isoformat()
            dupe["cdc_operation"] = "U"  # looks like an update
            dupes.append(dupe)
        logger.debug("Injected %d duplicate records", len(dupes))
        return records + dupes

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def extract(self) -> list[dict]:
        """Generate a batch of order records with controlled quality issues."""
        batch_size = self.src_cfg.records_per_batch
        start_id = random.randint(100_000, 999_999)

        records = [self._generate_order(start_id + i) for i in range(batch_size)]

        # Inject problems
        records = self._inject_late_arrivals(records)
        records = self._inject_nulls(records)
        records = self._inject_duplicates(records)

        # Stamp run_id
        for rec in records:
            rec["pipeline_run_id"] = self.run_id

        self.logger.info(
            "Generated %d CDC records (batch_size=%d + injected dupes)",
            len(records),
            batch_size,
            extra={"record_count": len(records), "pipeline_run_id": self.run_id},
        )
        return records

    def extract_customers(self, order_records: list[dict]) -> list[dict]:
        """Generate companion customer dimension records.

        De-duplicates by customer_id so each customer appears once.
        """
        seen: set[int] = set()
        customers: list[dict] = []
        for rec in order_records:
            cid = rec.get("customer_id")
            if cid is not None and cid not in seen:
                seen.add(cid)
                customers.append(self._generate_customer(cid))
        self.logger.info("Generated %d unique customer records", len(customers))
        return customers
