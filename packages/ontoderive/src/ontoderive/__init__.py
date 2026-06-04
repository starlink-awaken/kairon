"""OntoDerive — Ontology derivation engine for knowledge engineering.

Provides document abstraction, frontmatter detection/merging,
meta-validation, meta-evolution, and fault-tolerant pipeline tools.
"""

__version__ = "0.1.0"

__all__ = (
    "BaseDocument",
    "ChangeSemantics",
    "ChangeType",
    "DetectionResult",
    "DocGenerator",
    "DocumentMetadata",
    "DocumentType",
    "FaultContext",
    "FaultMode",
    "FrontmatterBlock",
    "FrontmatterDetector",
    "FrontmatterMerger",
    "IDocument",
    "ImpactLevel",
    "MarkdownDocument",
    "MetaValidateEngine",
    "Reference",
    "UpdateSuggestion",
    "__version__",
    "generate_doc",
)
