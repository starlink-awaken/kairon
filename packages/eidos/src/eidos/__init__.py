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

__all__ = (
    "Fact",
    "FieldType",
    "InferenceRule",
    "KnowledgeCard",
    "MetaRelationType",
    "MetaType",
    "OntologyNode",
    "Relation",
    "Schema",
    "SchemaField",
    "SchemaMigration",
    "SchemaRegistry",
    "StateMachine",
    "StateTransition",
    "ValidationError",
    "ValidationResult",
    "Validator",
    "create_registry",
    "get_migrations",
    "migrate_schema_instance",
    "register_migration",
    "registry",
)
