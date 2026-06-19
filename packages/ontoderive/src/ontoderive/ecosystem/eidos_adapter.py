"""Bidirectional bridge between OntoDerive models and Eidos types."""

from importlib.util import find_spec
from types import SimpleNamespace

EIDOS_AVAILABLE = find_spec("eidos.types") is not None


def is_eidos_available():
    return EIDOS_AVAILABLE


def to_eidos_fact(onto_fact):
    if not EIDOS_AVAILABLE:
        return None
    d = getattr(onto_fact, "data", {}) or {}
    return SimpleNamespace(
        id=getattr(onto_fact, "id", "f"),
        subject=d.get("subject", ""),
        predicate=d.get("predicate", "is"),
        object=d.get("object", ""),
        confidence=getattr(onto_fact, "weight", 1.0),
        source_card_id=getattr(onto_fact, "id", ""),
        derived_from="ontoderive",
    )


def from_eidos_fact(ef):
    return SimpleNamespace(
        id=getattr(ef, "id", ""),
        weight=getattr(ef, "confidence", 1.0),
        data={
            "subject": getattr(ef, "subject", ""),
            "predicate": getattr(ef, "predicate", "is"),
            "object": getattr(ef, "object", ""),
        },
    )


def from_eidos_entity(node):
    props = getattr(node, "properties", {}) or {}
    return SimpleNamespace(
        id=getattr(node, "id", ""),
        node_type=getattr(node, "node_type", "entity"),
        data={"name": getattr(node, "name", ""), **props},
        aliases=list(getattr(node, "aliases", []) or []),
    )


def to_eidos_entity(onto_entity):
    if not EIDOS_AVAILABLE:
        return None
    d = getattr(onto_entity, "data", {}) or {}
    return SimpleNamespace(
        id=getattr(onto_entity, "id", ""),
        name=d.get("name", ""),
        node_type=getattr(onto_entity, "node_type", "entity"),
        properties={k: v for k, v in d.items() if k != "name"},
    )
