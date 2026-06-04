"""Security best practices (toolkit skills/openai/security-best-practices.ts)."""

from __future__ import annotations


def validate_api_key(key: str, prefix: str = "sk-") -> bool:
    """Validate API key format."""
    return key.startswith(prefix) and len(key) > len(prefix)


def sanitize_input(text: str) -> str:
    """Basic input sanitization."""
    import html
    return html.escape(text)
