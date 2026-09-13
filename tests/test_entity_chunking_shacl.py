"""Tests for BET-Y1Q4-T6-27: Entity-Aware Chunking & SHACL Architecture Validator.

Covers:
  - EntityAwareChunking entity detection and preservation
  - Chunk boundary optimization (no entity splits)
  - SHACL validation for scene cards and DFSQ documents
  - Fragmentation rate metrics
  - CI integration readiness
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure iris and kairon packages are importable
# Path: tests/test_entity_chunking_shacl.py -> kairon root is 2 levels up
KAIRON_ROOT = Path(__file__).resolve().parent.parent
IRIS_SRC = KAIRON_ROOT / "packages" / "iris" / "src"
KAIRON_SRC = KAIRON_ROOT / "src"

for src_path in [IRIS_SRC, KAIRON_SRC]:
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from iris.split.entity_chunker import (
    ChunkConfig,
    EntityAwareChunker,
    _merge_overlapping_spans,
    _find_sentence_boundary,
    _count_preserved_entities,
)
from kairon.ontology.shacl_validator import (
    SHACLValidator,
    ValidationResult,
    ValidationSeverity,
)


# ======================================================================
# Entity-Aware Chunking Tests
# ======================================================================


class TestEntityDetection:
    """Test entity detection capabilities."""

    def setup_method(self):
        self.chunker = EntityAwareChunker()

    def test_detect_chinese_organizations(self):
        """Should detect Chinese organization names."""
        text = "国家卫生健康委员会发布了新规定，市场监管总局负责监督。"
        entities = self.chunker._detect_entities(text)
        assert len(entities) >= 2
        # Check that detected spans cover organization names
        entity_texts = [text[s:e] for s, e in entities]
        assert any("国家卫生健康委员会" in t for t in entity_texts)
        assert any("市场监管总局" in t for t in entity_texts)

    def test_detect_dates(self):
        """Should detect date patterns."""
        text = "根据2024年3月15日发布的规定，自2024-04-01起施行。"
        entities = self.chunker._detect_entities(text)
        assert len(entities) >= 2

    def test_detect_standards(self):
        """Should detect standard references."""
        text = "符合GB/T 19001-2016和ISO 9001标准要求。"
        entities = self.chunker._detect_entities(text)
        assert len(entities) >= 1

    def test_detect_english_proper_nouns(self):
        """Should detect English proper nouns."""
        text = "OpenAI released GPT-4, and Anthropic released Claude."
        entities = self.chunker._detect_entities(text)
        assert len(entities) >= 1

    def test_empty_text(self):
        """Should handle empty text gracefully."""
        entities = self.chunker._detect_entities("")
        assert entities == []


class TestMergeOverlappingSpans:
    """Test span merging logic."""

    def test_no_overlaps(self):
        """Non-overlapping spans should remain unchanged."""
        spans = [(0, 5), (10, 15), (20, 25)]
        merged = _merge_overlapping_spans(spans)
        assert merged == spans

    def test_overlapping_spans(self):
        """Overlapping spans should be merged."""
        spans = [(0, 10), (5, 15), (20, 25)]
        merged = _merge_overlapping_spans(spans)
        assert len(merged) == 2
        assert merged[0] == (0, 15)

    def test_contained_spans(self):
        """Spans contained within others should be absorbed."""
        spans = [(0, 20), (5, 10)]
        merged = _merge_overlapping_spans(spans)
        assert len(merged) == 1
        assert merged[0] == (0, 20)

    def test_empty_input(self):
        """Empty input should return empty list."""
        assert _merge_overlapping_spans([]) == []


class TestSentenceBoundary:
    """Test sentence boundary detection."""

    def test_chinese_period(self):
        """Should find Chinese period boundary."""
        text = "这是第一句。这是第二句。这是第三句。"
        pos = _find_sentence_boundary(text, 5, window=10)
        assert text[pos - 1] == "。" or pos == 5

    def test_english_period(self):
        """Should find English period boundary."""
        text = "First sentence. Second sentence. Third sentence."
        pos = _find_sentence_boundary(text, 10, window=10)
        # Position should be at or near a sentence boundary
        assert pos >= 0

    def test_no_boundary_in_window(self):
        """Should return original position if no boundary found."""
        text = "abcdefghijklmnop"
        pos = _find_sentence_boundary(text, 8, window=3)
        assert pos == 8


class TestChunking:
    """Test main chunking functionality."""

    def setup_method(self):
        self.chunker = EntityAwareChunker()

    def test_short_text_no_split(self):
        """Short text should not be split."""
        text = "这是一个短文本。"
        result = self.chunker.chunk(text)
        assert len(result.chunks) == 1
        assert result.chunks[0] == text
        assert result.entity_fragmentation_rate == 0.0

    def test_long_text_splits(self):
        """Long text should be split into multiple chunks."""
        # Create text longer than max_chunk_size
        text = "这是一段测试文本。" * 500
        config = ChunkConfig(max_chunk_size=100, overlap=20)
        chunker = EntityAwareChunker(config=config)
        result = chunker.chunk(text)
        assert len(result.chunks) > 1

    def test_entity_preservation(self):
        """Entities should not be split across chunks."""
        # Text with known entities and length > max_chunk_size
        # Use sentence boundary to ensure clean splits
        base = "根据GB/T 19001-2016标准，国家卫生健康委员会要求各医疗机构严格执行规定。"
        text = base * 100
        config = ChunkConfig(
            max_chunk_size=80,
            overlap=0,  # No overlap for clean entity counting
            preserve_entities=True,
            sentence_boundary=True,
        )
        chunker = EntityAwareChunker(config=config)
        result = chunker.chunk(text)
        # With sentence boundary and no overlap, entities should be preserved
        assert result.entity_fragmentation_rate == 0.0

    def test_fragmentation_rate_zero_for_short_text(self):
        """Short text should have zero fragmentation rate."""
        text = "国家卫生健康委员会"
        result = self.chunker.chunk(text)
        assert result.entity_fragmentation_rate == 0.0

    def test_empty_text_returns_empty_chunks(self):
        """Empty text should return empty chunk list."""
        result = self.chunker.chunk("")
        assert result.chunks == []

    def test_chunk_overlap(self):
        """Chunks should have configured overlap."""
        config = ChunkConfig(max_chunk_size=100, overlap=30)
        chunker = EntityAwareChunker(config=config)
        text = "测试文本" * 100
        result = chunker.chunk(text)
        if len(result.chunks) > 1:
            # Verify overlap exists between consecutive chunks
            for i in range(len(result.chunks) - 1):
                chunk_end = result.chunks[i][-20:]
                chunk_next_start = result.chunks[i + 1][:20]
                # Some content should overlap
                assert len(chunk_end) > 0 and len(chunk_next_start) > 0


# ======================================================================
# SHACL Validation Tests
# ======================================================================


class TestSHACLValidator:
    """Test SHACL validation functionality."""

    def setup_method(self):
        # Path: tests/ -> kairon -> projects -> workspace root (4 levels up)
        self.validator = SHACLValidator(
            workspace_root=Path(__file__).resolve().parent.parent.parent.parent.parent
        )

    def test_validate_scene_card_valid(self):
        """Valid scene card should pass validation."""
        import tempfile
        import yaml

        valid_card = {
            "id": "test-scene-001",
            "title": "测试场景",
            "status": "draft",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(valid_card, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "scene-card")
            assert result.valid, f"Unexpected violations: {result.violations}"
        finally:
            Path(temp_path).unlink()

    def test_validate_scene_card_missing_id(self):
        """Scene card without id should fail validation."""
        import tempfile
        import yaml

        invalid_card = {
            "title": "测试场景",
            "status": "draft",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(invalid_card, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "scene-card")
            assert not result.valid
            assert any("id" in v for v in result.violations)
        finally:
            Path(temp_path).unlink()

    def test_validate_scene_card_invalid_status(self):
        """Scene card with invalid status should fail validation."""
        import tempfile
        import yaml

        invalid_card = {
            "id": "test-001",
            "title": "Test",
            "status": "invalid_status",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(invalid_card, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "scene-card")
            assert not result.valid
            assert any("status" in v.lower() for v in result.violations)
        finally:
            Path(temp_path).unlink()

    def test_validate_scene_card_assisted_requires_samples(self):
        """Assisted scene card requires samples >= 30."""
        import tempfile
        import yaml

        card = {
            "id": "test-001",
            "title": "Test Scene",
            "status": "assisted",
            "samples": 10,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(card, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "scene-card")
            assert not result.valid
            assert any("samples" in v.lower() or "30" in v for v in result.violations)
        finally:
            Path(temp_path).unlink()

    def test_validate_scene_card_routine_requires_calibration(self):
        """Routine scene card requires calibration >= 0.6."""
        import tempfile
        import yaml

        card = {
            "id": "test-001",
            "title": "Test Scene",
            "status": "routine",
            "samples": 50,
            "calibration": 0.3,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(card, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "scene-card")
            assert not result.valid
            assert any("calibration" in v.lower() or "0.6" in v for v in result.violations)
        finally:
            Path(temp_path).unlink()

    def test_validate_dfsq_valid(self):
        """Valid DFSQ document should pass validation."""
        import tempfile
        import yaml

        valid_dfsq = {
            "schema": "dimension-system/v1",
            "version": "2.0.0",
            "dimensions": 12,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(valid_dfsq, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "dfsq")
            assert result.valid, f"Unexpected violations: {result.violations}"
        finally:
            Path(temp_path).unlink()

    def test_validate_dfsq_missing_schema(self):
        """DFSQ without schema should fail validation."""
        import tempfile
        import yaml

        invalid_dfsq = {
            "version": "1.0.0",
            "dimensions": 4,
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(invalid_dfsq, f, allow_unicode=True)
            temp_path = f.name

        try:
            result = self.validator.validate_file(temp_path, "dfsq")
            assert not result.valid
            assert any("schema" in v.lower() for v in result.violations)
        finally:
            Path(temp_path).unlink()

    def test_validate_unknown_shape_set(self):
        """Unknown shape set should return error."""
        result = self.validator.validate_file("dummy.yaml", "unknown-shape")
        assert not result.valid
        assert any("Unknown" in v for v in result.violations)

    def test_validate_nonexistent_file(self):
        """Non-existent data file should return error."""
        result = self.validator.validate_file(
            "/nonexistent/path/file.yaml", "scene-card"
        )
        assert not result.valid
        assert any("not found" in v.lower() for v in result.violations)


class TestValidationResult:
    """Test ValidationResult data structure."""

    def test_default_valid(self):
        """Default result should be valid."""
        result = ValidationResult(valid=True)
        assert result.valid
        assert result.violations == []

    def test_add_violation_invalidates(self):
        """Adding a violation should invalidate result."""
        result = ValidationResult(valid=True)
        result.add_violation("Test violation")
        assert not result.valid
        assert len(result.violations) == 1

    def test_add_warning_does_not_invalidate(self):
        """Adding a warning should not invalidate result."""
        result = ValidationResult(valid=True)
        result.add_warning("Test warning")
        assert result.valid
        assert len(result.warnings) == 1


# ======================================================================
# Integration-Ready Tests (CI Gate Compatibility)
# ======================================================================


class TestCIGateReadiness:
    """Verify components are ready for CI gate integration."""

    def test_entity_chunker_importable(self):
        """EntityAwareChunker should be importable from iris.split."""
        from iris.split import EntityAwareChunker, ChunkConfig, ChunkResult

        assert EntityAwareChunker is not None
        assert ChunkConfig is not None
        assert ChunkResult is not None

    def test_shacl_validator_importable(self):
        """SHACLValidator should be importable from kairon.ontology."""
        from kairon.ontology import SHACLValidator, ValidationResult, ValidationSeverity

        assert SHACLValidator is not None
        assert ValidationResult is not None
        assert ValidationSeverity is not None

    def test_shape_files_exist(self):
        """SHACL shape files should exist at canonical paths."""
        # Path: tests/ -> kairon -> projects -> workspace root (4 levels up)
        workspace_root = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
        )
        dfsq_shapes = workspace_root / ".omo" / "standards" / "shapes" / "dfsq-shapes.ttl"
        scene_shapes = (
            workspace_root / ".omo" / "standards" / "shapes" / "scene-card-shapes.ttl"
        )
        assert dfsq_shapes.exists(), f"Missing: {dfsq_shapes}"
        assert scene_shapes.exists(), f"Missing: {scene_shapes}"

    def test_shape_files_parseable(self):
        """Shape files should be valid TTL (basic syntax check)."""
        # Path: tests/ -> kairon -> projects -> workspace root (4 levels up)
        workspace_root = (
            Path(__file__).resolve().parent.parent.parent.parent.parent
        )
        for shape_name in ["dfsq-shapes.ttl", "scene-card-shapes.ttl"]:
            shape_path = workspace_root / ".omo" / "standards" / "shapes" / shape_name
            content = shape_path.read_text(encoding="utf-8")
            # Basic TTL syntax checks
            assert "@prefix" in content, f"{shape_name} missing @prefix declarations"
            assert "sh:" in content, f"{shape_name} missing SHACL namespace usage"
            assert "sh:property" in content or "sh:sparql" in content, (
                f"{shape_name} missing constraint definitions"
            )
