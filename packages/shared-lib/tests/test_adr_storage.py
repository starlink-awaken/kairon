"""Tests for kairon_lib.adr_storage — SQLiteADRStorage."""

import pytest
from kairon_lib.adr_storage import (
    ADR_DECIDED,
    ADR_DRAFT,
    ADR_REVIEW,
    ADR_SUPERSEDED,
    SQLiteADRStorage,
)


class TestADRStorage:
    """Tests for SQLiteADRStorage."""

    @pytest.fixture
    def store(self, tmp_path):
        db = str(tmp_path / "test_adrs.db")
        return SQLiteADRStorage(db_path=db)

    def test_create_and_get(self, store):
        adr = store.create("Test ADR", "Some context", author="@Tester")
        assert adr.title == "Test ADR"
        assert adr.context == "Some context"
        assert adr.author == "@Tester"
        assert adr.status == ADR_DRAFT
        assert adr.id.startswith("ADR-")

        fetched = store.get(adr.id)
        assert fetched is not None
        assert fetched.title == adr.title
        assert fetched.status == ADR_DRAFT

    def test_get_nonexistent(self, store):
        assert store.get("NONEXISTENT") is None

    def test_list_all(self, store):
        store.create("ADR 1", "ctx1")
        store.create("ADR 2", "ctx2")
        all_adrs = store.list()
        assert len(all_adrs) == 2

    def test_list_filter_by_status(self, store):
        a1 = store.create("Title A", "ctx")
        store.transition(a1.id, ADR_REVIEW)
        store.create("Title B", "ctx")
        drafts = store.list(status=ADR_DRAFT)
        reviews = store.list(status=ADR_REVIEW)
        assert len(drafts) == 1
        assert len(reviews) == 1
        assert drafts[0].title == "Title B"
        assert reviews[0].title == "Title A"

    def test_update_decision(self, store):
        adr = store.create("Update ADR", "context")
        ok = store.update(adr.id, decision="We chose X", consequences="Need to update docs")
        assert ok is True
        updated = store.get(adr.id)
        assert updated is not None
        assert updated.decision == "We chose X"
        assert updated.consequences == "Need to update docs"

    def test_update_nonexistent(self, store):
        assert store.update("NOPE", decision="x") is False

    def test_transition_forward(self, store):
        adr = store.create("Transitions", "ctx")
        assert store.transition(adr.id, ADR_REVIEW) is True
        assert store.get(adr.id).status == ADR_REVIEW
        assert store.transition(adr.id, ADR_DECIDED) is True
        assert store.get(adr.id).status == ADR_DECIDED
        assert store.transition(adr.id, ADR_SUPERSEDED) is True
        assert store.get(adr.id).status == ADR_SUPERSEDED

    def test_transition_invalid_skip(self, store):
        adr = store.create("Skip test", "ctx")
        # DRAFT -> DECIDED is invalid (must go through REVIEW)
        assert store.transition(adr.id, ADR_DECIDED) is False
        assert store.get(adr.id).status == ADR_DRAFT

    def test_transition_review_back_to_draft(self, store):
        adr = store.create("Rework", "ctx")
        store.transition(adr.id, ADR_REVIEW)
        assert store.transition(adr.id, ADR_DRAFT) is True
        assert store.get(adr.id).status == ADR_DRAFT

    def test_transition_nonexistent(self, store):
        assert store.transition("GHOST", ADR_REVIEW) is False

    def test_transition_unknown_status(self, store):
        adr = store.create("Bad status", "ctx")
        assert store.transition(adr.id, "UNKNOWN") is False

    def test_search_basic(self, store):
        store.create("Auth redesign", "OAuth2 migration", author="@Prime")
        store.create("Cache layer", "Redis integration", author="@Devil")
        results = store.search("auth")
        assert len(results) == 1
        assert results[0].title == "Auth redesign"

    def test_search_across_context(self, store):
        store.create("API Gateway", "Rate limiting for REST endpoints")
        results = store.search("REST")
        assert len(results) == 1

    def test_empty_search_returns_empty(self, store):
        assert store.search("nothing") == []

    def test_multiple_adrs_independent(self, store):
        a1 = store.create("ADR 1", "c1")
        a2 = store.create("ADR 2", "c2")
        assert a1.id != a2.id
        assert len(store.list()) == 2
