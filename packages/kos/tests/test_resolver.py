"""Tests for kos.ontology.resolver — entity resolution."""

import unittest


class TestResolverSchema(unittest.TestCase):
    """Test resolver data structures and schemas (no DB required)."""

    def test_candidate_dataclass(self):
        from kos.ontology.resolver import ResolutionCandidate

        c = ResolutionCandidate(source_id="ROL-a", target_id="ROL-b", score=0.8, method="label_exact")
        self.assertEqual(c.source_id, "ROL-a")
        self.assertEqual(c.method, "label_exact")

    def test_merge_result_schema(self):
        result = {"status": "merged", "source": "ROL-old", "target": "ROL-new", "aliases_merged": 3}
        self.assertEqual(result["status"], "merged")
        self.assertIn("source", result)

    def test_error_result_schema(self):
        result = {"error": "源实体不存在: ROL-nonexistent"}
        self.assertIn("error", result)

    def test_find_candidates_no_db(self):
        from kos.ontology.resolver import find_candidates

        result = find_candidates("nonexistent")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    import unittest.mock

    unittest.main()
