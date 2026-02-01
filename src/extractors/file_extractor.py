"""GCS file extractor for supplier catalog CSVs.

In production this watches a GCS bucket for new CSV files matching a
prefix.  For local development it reads from a ``data/supplier/`` directory.

The extractor tracks which files have already been processed via a simple
manifest file so it only picks up *new* drops.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from src.config import AppConfig
from src.extractors import BaseExtractor

logger = logging.getLogger(__name__)


class FileExtractor(BaseExtractor):
    """Extract supplier catalog data from CSV files."""

    source_name = "supplier_catalog"  # type: ignore[assignment]

    def __init__(
        self,
        config: AppConfig,
        run_id: str,
        *,
        local_dir: str | Path | None = None,
    ) -> None:
        super().__init__(config, run_id)
        self.src_cfg = config.sources.supplier_catalog
        # Local mode: read from filesystem instead of GCS
        self.local_dir = Path(local_dir) if local_dir else None
        self._manifest_path = Path("data/.file_manifest.json")

    # ------------------------------------------------------------------
    # Manifest — tracks already-processed files
    # ------------------------------------------------------------------
    def _load_manifest(self) -> set[str]:
        if self._manifest_path.exists():
            return set(json.loads(self._manifest_path.read_text()))
        return set()

    def _save_manifest(self, processed: set[str]) -> None:
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(json.dumps(sorted(processed)))

    # ------------------------------------------------------------------
    # Local file discovery
    # ------------------------------------------------------------------
    def _discover_local_files(self) -> list[Path]:
        if self.local_dir is None or not self.local_dir.exists():
            return []
        prefix = self.src_cfg.file_prefix
        return sorted(p for p in self.local_dir.glob(f"{prefix}*.csv") if p.is_file())

    def _read_csv(self, path: Path) -> list[dict]:
        """Read a CSV file into a list of dicts, validating expected columns."""
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            self.logger.warning("Empty CSV file: %s", path.name)
            return []

        # Validate that expected columns are present
        actual = set(rows[0].keys())
        expected = set(self.src_cfg.expected_columns)
        missing = expected - actual
        if missing:
            self.logger.error("CSV %s missing columns: %s", path.name, missing)
            # Still return rows — validator will quarantine bad records
        return rows

    # ------------------------------------------------------------------
    # GCS discovery (stub — replace with google-cloud-storage calls)
    # ------------------------------------------------------------------
    def _discover_gcs_files(self) -> list[str]:
        """List new blobs in the supplier catalog GCS prefix.

        TODO: Replace with actual GCS client calls when deploying:
            from google.cloud import storage
            client = storage.Client(project=self.config.gcp.project_id)
            bucket = client.bucket(self.config.storage.bronze_bucket)
            blobs = bucket.list_blobs(prefix=f"supplier_catalog/")
        """
        self.logger.info("GCS file discovery not yet implemented — use local_dir")
        return []

    def _read_gcs_csv(self, blob_name: str) -> list[dict]:
        """Read a CSV blob from GCS into a list of dicts.

        TODO: Implement with google.cloud.storage:
            bucket = client.bucket(self.config.storage.bronze_bucket)
            blob = bucket.blob(blob_name)
            content = blob.download_as_text()
            reader = csv.DictReader(io.StringIO(content))
            return list(reader)
        """
        return []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def extract(self) -> list[dict]:
        """Discover new CSV files and read their contents."""
        manifest = self._load_manifest()
        all_records: list[dict] = []

        if self.local_dir:
            files = self._discover_local_files()
            for path in files:
                if path.name in manifest:
                    self.logger.debug("Skipping already-processed: %s", path.name)
                    continue
                rows = self._read_csv(path)
                for row in rows:
                    row["source_file"] = path.name
                    row["pipeline_run_id"] = self.run_id
                all_records.extend(rows)
                manifest.add(path.name)
        else:
            blobs = self._discover_gcs_files()
            for blob_name in blobs:
                if blob_name in manifest:
                    continue
                rows = self._read_gcs_csv(blob_name)
                for row in rows:
                    row["source_file"] = blob_name
                    row["pipeline_run_id"] = self.run_id
                all_records.extend(rows)
                manifest.add(blob_name)

        self._save_manifest(manifest)

        self.logger.info(
            "Extracted %d supplier catalog records from %d new files",
            len(all_records),
            len([f for f in manifest]) - len(manifest - set()),
            extra={"record_count": len(all_records), "pipeline_run_id": self.run_id},
        )
        return all_records
