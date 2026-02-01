"""GCS loader — writes validated records as Parquet to bronze storage.

In production, writes to ``gs://<bronze_bucket>/<source>/dt=YYYY-MM-DD/``.
For local development, writes to ``data/bronze/<source>/dt=YYYY-MM-DD/``.

Design decisions
----------------
* Hive-style partitioning (``dt=`` prefix) so downstream tools (Spark,
  BigQuery external tables) can do partition pruning.
* Files are *never overwritten* — each run produces a new file named by
  ``pipeline_run_id``.  This guarantees bronze immutability.
* Quarantined records go to a separate bucket/directory.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.config import AppConfig

logger = logging.getLogger(__name__)


class GCSLoader:
    """Write Parquet files to GCS bronze layer (or local filesystem)."""

    def __init__(
        self,
        config: AppConfig,
        run_id: str,
        *,
        local_mode: bool = True,
        local_root: str | Path = "data",
    ) -> None:
        self.config = config
        self.run_id = run_id
        self.local_mode = local_mode
        self.local_root = Path(local_root)

    # ------------------------------------------------------------------
    # Local writers
    # ------------------------------------------------------------------
    def _write_local_parquet(
        self,
        records: list[dict],
        source_name: str,
        *,
        quarantine: bool = False,
    ) -> Path:
        """Write records as a Parquet file to a local Hive-partitioned path."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        bucket = "quarantine" if quarantine else "bronze"
        dir_path = self.local_root / bucket / source_name / f"dt={today}"
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{self.run_id}.parquet"
        filepath = dir_path / filename

        table = pa.Table.from_pylist(records)
        pq.write_table(table, filepath)

        logger.info(
            "Wrote %d records to %s",
            len(records),
            filepath,
            extra={"pipeline_run_id": self.run_id, "record_count": len(records)},
        )
        return filepath

    def _write_local_json(
        self,
        records: list[dict],
        source_name: str,
        *,
        quarantine: bool = False,
    ) -> Path:
        """Fallback: write as JSONL when records contain non-Arrow-friendly types."""
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        bucket = "quarantine" if quarantine else "bronze"
        dir_path = self.local_root / bucket / source_name / f"dt={today}"
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{self.run_id}.jsonl"
        filepath = dir_path / filename

        with open(filepath, "w") as f:
            for rec in records:
                f.write(json.dumps(rec, default=str) + "\n")

        logger.info(
            "Wrote %d records (JSONL) to %s",
            len(records),
            filepath,
            extra={"pipeline_run_id": self.run_id, "record_count": len(records)},
        )
        return filepath

    # ------------------------------------------------------------------
    # GCS writers (stubs — implement with google-cloud-storage)
    # ------------------------------------------------------------------
    def _write_gcs_parquet(
        self,
        records: list[dict],
        source_name: str,
        *,
        quarantine: bool = False,
    ) -> str:
        """Write Parquet to GCS.

        TODO: Implement with google.cloud.storage:
            from google.cloud import storage
            client = storage.Client(project=self.config.gcp.project_id)
            bucket_name = (self.config.storage.quarantine_bucket
                          if quarantine
                          else self.config.storage.bronze_bucket)
            bucket = client.bucket(bucket_name)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            blob_path = f"{source_name}/dt={today}/{self.run_id}.parquet"
            # Write to temp file then upload
        """
        raise NotImplementedError("GCS write not yet implemented — use local_mode=True")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def load_bronze(self, records: list[dict], source_name: str) -> Path | str:
        """Write valid records to bronze layer."""
        if not records:
            logger.warning("No records to write for %s", source_name)
            return Path()

        if self.local_mode:
            try:
                return self._write_local_parquet(records, source_name)
            except (pa.ArrowInvalid, pa.ArrowTypeError):
                logger.warning("Arrow conversion failed — falling back to JSONL")
                return self._write_local_json(records, source_name)
        return self._write_gcs_parquet(records, source_name)

    def load_quarantine(self, records: list[dict], source_name: str) -> Path | str:
        """Write quarantined records to quarantine layer."""
        if not records:
            return Path()

        if self.local_mode:
            return self._write_local_json(records, source_name, quarantine=True)
        return self._write_gcs_parquet(records, source_name, quarantine=True)
