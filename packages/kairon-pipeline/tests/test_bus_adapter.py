"""Tests for kairon_pipeline bus_adapter (R80 backlog fix).

The bus_adapter was added in R61 as part of the cross-repo bus
adoption (Phase B migration), but it had no tests at the time.
22 months later (R80), we're adding the missing coverage so that
future changes to the adapter are guarded by regression tests.
"""
from unittest.mock import patch


class TestBusAdapter:
    def test_imports_succeed(self):
        """Adapter imports without side-effects at module load."""
        from kairon_pipeline import bus_adapter
        # The real public functions (verified by reading bus_adapter.py)
        assert hasattr(bus_adapter, "emit_source_ingested")
        assert hasattr(bus_adapter, "emit_extraction_completed")
        assert hasattr(bus_adapter, "emit_quality_gate_result")
        assert hasattr(bus_adapter, "emit_event")

    def test_emit_source_ingested_dispatches_envelope(self):
        """emit_source_ingested() should call publish() with a
        properly-shaped BusEnvelope."""
        from kairon_pipeline import bus_adapter

        with patch("kairon_pipeline.bus_adapter.emit_event") as mock_publish:
            result = bus_adapter.emit_source_ingested(
                source_name="gdelt",
                record_count=1234,
            )
        mock_publish.assert_called_once()
        envelope = mock_publish.call_args[0][0]
        assert envelope.type == "kairon_pipeline:source_ingested"
        assert envelope.source == "kairon-pipeline"
        assert envelope.payload["source_name"] == "gdelt"
        assert envelope.payload["record_count"] == 1234
        # Function returns the event_id from publish
        assert result == envelope.id

    def test_emit_extraction_completed_dispatches_envelope(self):
        """emit_extraction_completed() should call publish()."""
        from kairon_pipeline import bus_adapter

        with patch("kairon_pipeline.bus_adapter.emit_event") as mock_publish:
            bus_adapter.emit_extraction_completed(
                pipeline_id="harvest-2026-06-13",
                extractor="html-clean",
                duration_ms=12500,
            )
        mock_publish.assert_called_once()
        envelope = mock_publish.call_args[0][0]
        assert envelope.type == "kairon:extraction:completed"
        assert envelope.payload["extractor"] == "html-clean"
        assert envelope.payload["duration_ms"] == 12500

    def test_emit_quality_gate_result_passed(self):
        """When a quality gate passes, the envelope payload says so."""
        from kairon_pipeline import bus_adapter

        with patch("kairon_pipeline.bus_adapter.emit_event") as mock_publish:
            bus_adapter.emit_quality_gate_result(
                pipeline_id="harvest-2026-06-13",
                gate="quality",
                passed=True,
            )
        mock_publish.assert_called_once()
        envelope = mock_publish.call_args[0][0]
        assert envelope.type == "kairon:quality:gate_result"
        assert envelope.payload["passed"] is True

    def test_emit_quality_gate_result_records_rejection(self):
        """When a quality gate fails, the rejection reason is in payload."""
        from kairon_pipeline import bus_adapter

        with patch("kairon_pipeline.bus_adapter.emit_event") as mock_publish:
            bus_adapter.emit_quality_gate_result(
                pipeline_id="harvest-fail",
                gate="quality",
                passed=False,
                rejection_reason="3 records below threshold",
            )
        envelope = mock_publish.call_args[0][0]
        assert envelope.payload["passed"] is False
        assert envelope.payload["rejection_reason"] == "3 records below threshold"

    def test_publish_failure_does_not_propagate(self):
        """If publish() raises (e.g., agora.bus unavailable), the
        adapter should NOT propagate the exception — it should
        log and continue. Pipeline must not abort on bus failure."""
        from kairon_pipeline import bus_adapter

        with patch(
            "kairon_pipeline.bus_adapter.emit_event",
            side_effect=ConnectionError("agora unreachable"),
        ):
            # Should not raise — the adapter is intentionally
            # besteffort: the pipeline is the source of truth, the
            # bus is a notification channel.
            bus_adapter.emit_source_ingested(
                source_name="gdelt",
                record_count=0,
            )
