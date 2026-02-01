"""Open Exchange Rates API extractor.

Pulls daily exchange rates and converts them into a flat list of records
(one per currency pair) for downstream loading.

Retry strategy: exponential backoff via ``tenacity`` (3 attempts,
wait 5 → 10 → 20 s). On permanent failure the task raises so Airflow
can handle retries at the DAG level.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import AppConfig
from src.extractors import BaseExtractor

logger = logging.getLogger(__name__)


class ExchangeRatesExtractor(BaseExtractor):
    """Extract daily FX rates from Open Exchange Rates API."""

    source_name = "exchange_rates"  # type: ignore[assignment]

    def __init__(self, config: AppConfig, run_id: str) -> None:
        super().__init__(config, run_id)
        self.src_cfg = config.sources.exchange_rates

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=60),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _fetch(self) -> dict:
        """HTTP GET with retries."""
        url = self.src_cfg.api_url
        params = {"app_id": self.src_cfg.api_key}
        self.logger.info("Fetching exchange rates from %s", url)

        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def extract(self) -> list[dict]:
        """Return one record per currency code with its USD rate."""
        payload = self._fetch()
        base_currency: str = payload.get("base", "USD")
        rates: dict[str, float] = payload.get("rates", {})
        timestamp = datetime.fromtimestamp(payload.get("timestamp", 0), tz=UTC)

        records = []
        for code, rate in rates.items():
            records.append(
                {
                    "currency_code": code,
                    "rate_to_usd": rate,
                    "base_currency": base_currency,
                    "rate_date": timestamp.date().isoformat(),
                    "fetched_at": self._now_utc().isoformat(),
                    "pipeline_run_id": self.run_id,
                }
            )

        self.logger.info(
            "Extracted %d exchange rates for %s",
            len(records),
            timestamp.date(),
            extra={"record_count": len(records), "pipeline_run_id": self.run_id},
        )
        return records
