"""Unit tests for PipelineMetrics."""

from __future__ import annotations

from src.utils.metrics import PipelineMetrics


class TestPipelineMetrics:
    """Test run metadata tracking."""

    def test_generates_uuid_run_id(self) -> None:
        m = PipelineMetrics()
        assert len(m.run_id) == 36  # UUID format

    def test_starts_as_running(self) -> None:
        m = PipelineMetrics()
        assert m.status == "RUNNING"

    def test_finish_sets_end_time(self) -> None:
        m = PipelineMetrics()
        m.finish("SUCCESS")
        assert m.end_time is not None
        assert m.status == "SUCCESS"

    def test_duration_calculated(self) -> None:
        m = PipelineMetrics()
        m.finish()
        assert m.duration_seconds is not None
        assert m.duration_seconds >= 0

    def test_to_dict_serializable(self) -> None:
        m = PipelineMetrics()
        m.records_extracted = 100
        m.finish()
        d = m.to_dict()
        assert d["records_extracted"] == 100
        assert "run_id" in d
