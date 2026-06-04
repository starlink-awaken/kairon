"""KOS Ontology Module — entity extraction, reasoning, and management.

Package structure:
  engine.py     — Legacy CLI engine (extract, infer, card, path, discover, list)
  store.py      — Entity/Relation CRUD against KOS SQLite database
  _types.py     — Entity/Relation type definitions (from SPEC-v0.1 §3)
  resolver.py   — sameAs detection and entity merging (§4.4)
  discover.py   — Implicit relation discovery via co-occurrence (§4.5)
  export.py     — JSON-LD / Turtle / summary export (§4.6)
  api.py        — CLI/MCP action dispatcher (§4.7)

Use:
  from kos.ontology import engine       # CLI operations
  from kos.ontology.store import ...    # CRUD operations
  from kos.ontology.resolver import find_candidates, merge_entities
  from kos.ontology.discover import discover_implicit_relations
  from kos.ontology.export import export_jsonld, export_turtle
  from kos.ontology.api import handle_action
"""

from kos.ontology.store import (  # noqa: F401
    delete_entity,
    get_entity,
    get_relations,
    import_entities,
    put_entity,
    put_relation,
    search_entities,
)
