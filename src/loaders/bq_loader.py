"""BigQuery loader — loads validated records into staging tables.

Provides both:
* ``load_from_parquet`` — load a local/GCS Parquet file into BQ.
* ``load_from_records`` — load a list of dicts directly via the
  streaming insert API (useful for small batches / dev).

Watermark management
--------------------
``get_watermark`` / ``update_watermark`` track the high-water mark in
a ``metadata.etl_watermarks`` table so incremental extraction only pulls
new records.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from src.config import AppConfig

logger = logging.getLogger(__name__)


class BigQueryLoader:
    """Load data into BigQuery staging tables."""

    def __init__(self, config: AppConfig, run_id: str) -> None:
        self.config = config
        self.run_id = run_id
        self.project = config.gcp.project_id
        self._client = None

    @property
    def client(self):  # type: ignore[no-untyped-def]
        """Lazy-init BigQuery client."""
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project)
        return self._client

    # ------------------------------------------------------------------
    # Watermark management
    # ------------------------------------------------------------------
    def get_watermark(self, table_name: str) -> datetime:
        """Retrieve the last successful load timestamp from metadata."""
        query = f"""
            SELECT last_loaded_at
            FROM `{self.project}.{self.config.bigquery.metadata_dataset}.etl_watermarks`
            WHERE table_name = '{table_name}'
        """
        try:
            result = self.client.query(query).result()
            row = next(iter(result), None)
            return row.last_loaded_at if row else datetime.min.replace(tzinfo=UTC)
        except Exception:
            logger.warning("Watermark table not found — returning epoch")
            return datetime.min.replace(tzinfo=UTC)

    def update_watermark(self, table_name: str, new_watermark: datetime) -> None:
        """Upsert the watermark after successful extraction."""
        query = f"""
            MERGE `{self.project}.{self.config.bigquery.metadata_dataset}.etl_watermarks` AS target
            USING (
                SELECT '{table_name}' AS table_name,
                       TIMESTAMP('{new_watermark.isoformat()}') AS last_loaded_at
            ) AS source
            ON target.table_name = source.table_name
            WHEN MATCHED THEN
                UPDATE SET last_loaded_at = source.last_loaded_at
            WHEN NOT MATCHED THEN
                INSERT (table_name, last_loaded_at)
                VALUES (source.table_name, source.last_loaded_at)
        """
        self.client.query(query).result()
        logger.info(
            "Updated watermark for %s to %s",
            table_name,
            new_watermark.isoformat(),
        )

    # ------------------------------------------------------------------
    # Load methods
    # ------------------------------------------------------------------
    def load_from_records(
        self, records: list[dict], table_name: str, dataset: str | None = None
    ) -> int:
        """Load records via BigQuery streaming insert.

        Good for small batches in dev.  For production volumes, prefer
        ``load_from_parquet`` with a load job.
        """
        if not records:
            return 0

        ds = dataset or self.config.bigquery.staging_dataset
        table_ref = f"{self.project}.{ds}.{table_name}"

        errors = self.client.insert_rows_json(table_ref, records)
        if errors:
            logger.error("BigQuery insert errors: %s", errors)
            raise RuntimeError(f"BigQuery streaming insert failed: {errors}")

        logger.info(
            "Loaded %d records into %s",
            len(records),
            table_ref,
            extra={"pipeline_run_id": self.run_id, "record_count": len(records)},
        )
        return len(records)

    def load_from_parquet(self, filepath: Path | str, table_name: str) -> int:
        """Load a Parquet file into BigQuery via a load job.

        This is the preferred method for production — more efficient than
        streaming inserts and supports schema auto-detection.
        """
        from google.cloud import bigquery

        ds = self.config.bigquery.staging_dataset
        table_ref = f"{self.project}.{ds}.{table_name}"

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )

        with open(filepath, "rb") as f:
            job = self.client.load_table_from_file(f, table_ref, job_config=job_config)
        job.result()  # Wait for completion

        logger.info(
            "Loaded Parquet %s into %s (%d rows)",
            filepath,
            table_ref,
            job.output_rows or 0,
            extra={"pipeline_run_id": self.run_id},
        )
        return job.output_rows or 0

    # ------------------------------------------------------------------
    # Metadata logging
    # ------------------------------------------------------------------
    def log_pipeline_run(self, metrics_dict: dict) -> None:
        """Insert a pipeline run record into the metadata table."""
        table_ref = f"{self.project}.{self.config.bigquery.metadata_dataset}.pipeline_runs"
        try:
            errors = self.client.insert_rows_json(table_ref, [metrics_dict])
            if errors:
                logger.error("Failed to log pipeline run: %s", errors)
        except Exception:
            logger.exception("Could not log pipeline run to BigQuery")
