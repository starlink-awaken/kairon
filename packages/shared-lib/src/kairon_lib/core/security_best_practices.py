from __future__ import annotations

from typing import Any

REFERENCES: list[dict[str, str]] = [
    {"topic": "OWASP Top 10", "file": "owasp-top-10.md", "loadWhen": "General security review"},
    {"topic": "Authentication", "file": "authentication.md", "loadWhen": "Auth-related code"},
    {"topic": "Authorization", "file": "authorization.md", "loadWhen": "Permission checks"},
]

SECURITY_BEST_PRACTICES_SKILL: dict[str, Any] = {
    "id": "security-best-practices",
    "name": "Security Best Practices",
    "description": "Use for security review, vulnerability detection, and secure coding guidance",
    "longDescription": "## Security Best Practices\n\nComprehensive security guidance for vulnerability detection, secure coding, and compliance.",
    "triggers": [
        "security", "secure", "vulnerability", "owasp", "audit",
        "authentication", "authorization", "encryption", "privacy",
        "compliance", "soc2", "gdpr", "pentest", "exploit",
        "安全", "漏洞", "审计", "加密", "认证",
    ],
    "role": "reviewer",
    "scope": "review",
    "outputFormat": "text",
    "category": "security",
    "dependencies": [],
    "references": REFERENCES,
    "mcpServers": [],
    "externalScripts": [],
    "yamlConfig": {
        "display_name": "Security Best Practices",
        "short_description": "Use for security review, vulnerability detection, and secure coding guidance",
        "default_prompt": "You are a security expert. Analyze the provided code for security vulnerabilities and suggest improvements.",
    },
}
