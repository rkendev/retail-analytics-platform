"""Abstract base class for data extractors.

Every extractor — API, CDC simulator, file watcher — implements this
interface so the pipeline runner can treat them uniformly.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from src.config import AppConfig


class BaseExtractor(ABC):
    """Contract for all data source extractors."""

    def __init__(self, config: AppConfig, run_id: str) -> None:
        self.config = config
        self.run_id = run_id
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name for logging (e.g. 'exchange_rates')."""
        ...

    @abstractmethod
    def extract(self) -> list[dict]:
        """Pull raw records from the source.

        Returns a list of dicts — one dict per record.
        Each dict will be validated and stamped with ``pipeline_run_id``
        downstream.
        """
        ...

    def _now_utc(self) -> datetime:
        return datetime.now(UTC)
