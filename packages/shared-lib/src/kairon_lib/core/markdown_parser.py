"""Markdown parser — parse markdown into structured memory (toolkit memory/adapters/MarkdownParser.ts)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MarkdownSection:
    level: int; title: str; content: str; subsections: list[MarkdownSection] = field(default_factory=list)  # noqa: E702


class MarkdownParser:
    """Parse markdown documents into structured sections."""

    @staticmethod
    def parse(text: str) -> list[MarkdownSection]:
        lines = text.split("\n"); sections: list[MarkdownSection] = []; stack: list[MarkdownSection] = []  # noqa: E702
        current_content: list[str] = []
        for line in lines:
            m = re.match(r"^(#{1,6})\s+(.+)$", line)
            if m:
                if current_content and stack:
                    stack[-1].content = "\n".join(current_content).strip()
                current_content = []
                level = len(m.group(1)); title = m.group(2)  # noqa: E702
                sec = MarkdownSection(level=level, title=title)  # type: ignore[call-arg]
                while stack and stack[-1].level >= level:
                    stack.pop()
                if stack:
                    stack[-1].subsections.append(sec)
                else:
                    sections.append(sec)
                stack.append(sec)
            else:
                current_content.append(line)
        if current_content and stack:
            stack[-1].content = "\n".join(current_content).strip()
        return sections

    @staticmethod
    def to_text(sections: list[MarkdownSection], indent: int = 0) -> str:
        result = []
        for sec in sections:
            result.append(f"{'  ' * indent}{'#' * sec.level} {sec.title}")
            if sec.content:
                result.append(f"{'  ' * (indent + 1)}{sec.content}")
            result.append(MarkdownParser.to_text(sec.subsections, indent + 1))
        return "\n".join(result)
