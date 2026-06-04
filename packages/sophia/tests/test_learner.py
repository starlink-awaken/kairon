"""Tests for Sophia learning loop."""

import shutil
import tempfile

from sophia.learner import ParadigmLearner, ResearchTrace


class TestParadigmLearner:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.learner = ParadigmLearner(trace_dir=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_and_retrieve(self):
        self.learner.record(
            ResearchTrace(
                query="Compare Rust vs Go",
                paradigm_name="Adaptive",
                operations=["decompose", "search", "verify"],
                source_count=5,
                quality_score=85,
                completed=True,
            )
        )
        traces = self.learner._load_traces(10)
        assert len(traces) == 1
        assert traces[0]["query"] == "Compare Rust vs Go"
        assert traces[0]["quality"] == 85

    def test_get_effective_ops(self):
        for i in range(5):
            self.learner.record(
                ResearchTrace(
                    query=f"Test {i}",
                    paradigm_name="Test",
                    operations=["decompose", "search", "verify"],
                    source_count=3,
                    quality_score=70 + i * 5,
                    completed=True,
                )
            )
        effective = self.learner.get_effective_ops(min_samples=3)
        assert len(effective) >= 1
        for score in effective.values():
            assert 70 <= score <= 100

    def test_suggest_paradigm(self):
        self.learner.record(
            ResearchTrace(
                query="Compare Python vs Node performance",
                paradigm_name="Adaptive",
                operations=["decompose", "search", "compare"],
                source_count=5,
                quality_score=88,
                completed=True,
            )
        )
        result = self.learner.suggest_paradigm("Compare Flutter vs React Native")
        assert result["sample_count"] >= 1
        assert result["confidence"] > 0
        assert len(result["recommended_ops"]) >= 1

    def test_empty_learner(self):
        result = self.learner.suggest_paradigm("Some new query")
        assert result["sample_count"] == 0
        assert result["confidence"] == 0
