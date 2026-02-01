"""Pipeline run metadata and metrics tracking.

Every pipeline execution gets a unique ``pipeline_run_id`` (UUID).
Metrics are accumulated during the run and can be persisted to BigQuery's
``metadata.pipeline_runs`` table for full audit trail.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class PipelineMetrics:
    """Accumulated metrics for a single pipeline run."""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    dag_id: str = "retail_analytics_daily"
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    status: str = "RUNNING"

    # Extraction counts
    records_extracted: int = 0
    records_validated: int = 0
    records_quarantined: int = 0
    records_loaded: int = 0

    # Per-source breakdowns
    source_counts: dict[str, int] = field(default_factory=dict)

    # Quality gate results
    quality_checks_passed: int = 0
    quality_checks_failed: int = 0

    def finish(self, status: str = "SUCCESS") -> None:
        """Mark the run as finished."""
        self.end_time = datetime.now(UTC)
        self.status = status

    @property
    def duration_seconds(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, object]:
        """Serialize for BigQuery insertion."""
        return {
            "run_id": self.run_id,
            "dag_id": self.dag_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "records_extracted": self.records_extracted,
            "records_validated": self.records_validated,
            "records_quarantined": self.records_quarantined,
            "records_loaded": self.records_loaded,
            "quality_checks_passed": self.quality_checks_passed,
            "quality_checks_failed": self.quality_checks_failed,
            "duration_seconds": self.duration_seconds,
        }
