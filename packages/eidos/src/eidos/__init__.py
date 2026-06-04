"""Eidos - Schema definition and validation layer for the Workspace knowledge foundation."""

__version__ = "0.1.0"

from .meta import MetaRelationType, MetaType
from .registry import create_registry, registry
from .schema import (
    FieldType,
    Schema,
    SchemaField,
    SchemaMigration,
    SchemaRegistry,
    get_migrations,
    migrate_schema_instance,
    register_migration,
)
from .types import Fact, InferenceRule, KnowledgeCard, OntologyNode, Relation, StateMachine, StateTransition
from .validator import (
    ValidationError,
    ValidationResult,
    Validator,
)

__all__ = [
    "Schema",
    "SchemaField",
    "FieldType",
    "SchemaRegistry",
    "SchemaMigration",
    "register_migration",
    "get_migrations",
    "migrate_schema_instance",
    "MetaType",
    "MetaRelationType",
    "KnowledgeCard",
    "Fact",
    "InferenceRule",
    "OntologyNode",
    "Relation",
    "StateMachine",
    "StateTransition",
    "create_registry",
    "registry",
    "Validator",
    "ValidationResult",
    "ValidationError",
]
