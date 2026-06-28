"""Tests for core-models knowledge graph."""

from core_models.knowledge_graph import KnowledgeGraph


def test_empty_graph():
    kg = KnowledgeGraph()
    assert isinstance(kg.entities, dict)
    assert isinstance(kg.relations, list)


def test_graph_with_entity():
    kg = KnowledgeGraph()
    kg.entities["test"] = {"name": "test"}
    assert "test" in kg.entities
