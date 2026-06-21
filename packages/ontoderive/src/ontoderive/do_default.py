"""P58-W0 ontoderive do_default — 真业务 (调 ontoderive engine 真模块)."""

from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 ontoderive do_default: 真调 FrontmatterDetector / MetaValidateEngine / generate_doc."""
    try:
        from ontoderive import __version__
        from ontoderive.doc_generator import DocGenerator, generate_doc
        from ontoderive.frontmatter_detector import FrontmatterDetector
        from ontoderive.frontmatter_merger import FrontmatterMerger
        from ontoderive.meta_validate import MetaValidateEngine
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "list_components")
    try:
        if action == "list_components":
            return {
                "_method": "do_default",
                "_action": "list_components",
                "FrontmatterDetector": FrontmatterDetector.__name__,
                "FrontmatterMerger": FrontmatterMerger.__name__,
                "MetaValidateEngine": MetaValidateEngine.__name__,
                "DocGenerator": DocGenerator.__name__,
                "generate_doc": generate_doc.__name__,
                "version": __version__,
            }
        if action == "detector":
            d = FrontmatterDetector()
            return {
                "_method": "do_default",
                "_action": "detector",
                "detector_type": type(d).__name__,
                "methods": [m for m in dir(d) if not m.startswith("_")][:10],
            }
        if action == "validator":
            v = MetaValidateEngine()
            return {
                "_method": "do_default",
                "_action": "validator",
                "validator_type": type(v).__name__,
                "methods": [m for m in dir(v) if not m.startswith("_")][:10],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
