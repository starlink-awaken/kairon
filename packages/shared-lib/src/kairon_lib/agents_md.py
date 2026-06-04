"""AGENTS.md document parsing, keyword extraction, and indexing.

Port of agentmesh/packages/toolkit/src/agents-md/ to Python.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

# ── Types ──────────────────────────────────────────────────────────────


@dataclass
class Section:
    id: str = ""
    title: str = ""
    level: int = 1
    content: str = ""
    start_line: int = 0
    end_line: int = 0
    importance: float = 0.0
    keywords: list[str] = field(default_factory=list)


@dataclass
class CompressedIndex:
    sections: list[Section] = field(default_factory=list)
    total_sections: int = 0
    compressed_size: int = 0
    original_size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentStats:
    total_lines: int = 0
    total_chars: int = 0
    total_sections: int = 0
    code_blocks: int = 0
    avg_section_length: float = 0.0


@dataclass
class Keyword:
    text: str = ""
    type_: str = "word"  # technical | ngram | word
    frequency: int = 0
    score: float = 0.0
    tfidf: float = 0.0
    idf: float = 0.0


@dataclass
class IndexedDocument:
    id: str = ""
    title: str = ""
    content: str = ""
    section_id: str = ""
    keywords: list[Keyword] = field(default_factory=list)
    importance: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str = ""
    title: str = ""
    content: str = ""
    score: float = 0.0
    section_id: str = ""
    highlights: list[str] = field(default_factory=list)


# ── DocumentParser ────────────────────────────────────────────────────


class DocumentParser:
    """Parse markdown documents into sections and compress to 8KB format."""

    def __init__(self, max_section_length: int = 2000, min_section_length: int = 100) -> None:
        self.max_section_length = max_section_length
        self.min_section_length = min_section_length

    def parse(self, content: str) -> list[Section]:
        sections: list[Section] = []
        lines = content.split("\n")
        current: Section | None = None
        current_content: list[str] = []

        for i, line in enumerate(lines):
            m = re.match(r"^(#{1,6})\s+(.+)$", line)
            if m:
                if current and current_content:
                    current.content = "\n".join(current_content).strip()
                    sections.append(self._calc_importance(current))
                level = len(m.group(1))
                title = m.group(2).strip()
                slug = re.sub(r"[^\w一-龥\s-]", "", title.lower())
                slug = re.sub(r"\s+", "-", slug)[:50] or f"section-{len(sections)}"
                current = Section(
                    id=slug,
                    title=title,
                    level=level,
                    start_line=i + 1,
                    end_line=i + 1,
                )
                current_content = []
            elif current:
                current_content.append(line)
                current.end_line = i + 1

        if current and current_content:
            current.content = "\n".join(current_content).strip()
            sections.append(self._calc_importance(current))

        if not sections and content.strip():
            sections.append(
                self._calc_importance(
                    Section(id="content", title="Content", level=1, content=content.strip(), start_line=1, end_line=len(lines))
                )
            )

        return sections

    def extract_code_blocks(self, content: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        lines = content.split("\n")
        in_block = False
        lang = ""
        code: list[str] = []
        start = 0
        for i, line in enumerate(lines):
            if line.startswith("```"):
                if not in_block:
                    in_block = True
                    lang = line[3:].strip() or "text"
                    code = []
                    start = i + 1
                else:
                    blocks.append({"language": lang, "code": "\n".join(code), "start_line": start})
                    in_block = False
            elif in_block:
                code.append(line)
        return blocks

    def _calc_importance(self, section: Section) -> Section:
        imp = 0.0
        if 0 < len(section.title) <= 30:
            imp += 0.2
        if len(section.content) >= self.min_section_length:
            imp += min(0.3, len(section.content) / 10000)
        important_keywords = [
            "usage", "install", "api", "config", "example",
            "important", "warning", "note", "tip",
        ]
        if any(kw in section.title.lower() for kw in important_keywords):
            imp += 0.15
        code_blocks = self.extract_code_blocks(section.content)
        imp += min(0.2, len(code_blocks) * 0.1)
        if re.search(r"^[*-]\s", section.content, re.MULTILINE):
            imp += 0.1
        if "|" in section.content:
            imp += 0.15
        section.importance = min(1.0, imp)
        return section

    def compress(self, sections: list[Section]) -> CompressedIndex:
        sorted_sections = sorted(sections, key=lambda s: s.importance, reverse=True)
        target_size = 8 * 1024
        selected: list[Section] = []
        current_size = 0
        for sec in sorted_sections:
            sec_size = len(sec.content) + len(sec.title) + 200
            if current_size + sec_size <= target_size:
                selected.append(sec)
                current_size += sec_size
            elif not selected:
                selected.append(Section(**{**sec.__dict__, "content": sec.content[: target_size - 300]}))
                break
            else:
                break
        selected.sort(key=lambda s: s.start_line)
        original_size = sum(len(s.content) + len(s.title) for s in sections)
        return CompressedIndex(
            sections=selected,
            total_sections=len(sections),
            compressed_size=current_size,
            original_size=original_size,
            metadata={
                "version": "1.0",
                "created_at": datetime.now(UTC).isoformat(),
                "format": "vercel-8kb",
            },
        )

    def get_stats(self, content: str) -> DocumentStats:
        lines = content.split("\n")
        sections = self.parse(content)
        code_blocks = self.extract_code_blocks(content)
        avg_len = sum(len(s.content) for s in sections) / len(sections) if sections else 0
        return DocumentStats(
            total_lines=len(lines),
            total_chars=len(content),
            total_sections=len(sections),
            code_blocks=len(code_blocks),
            avg_section_length=avg_len,
        )


# ── KeywordExtractor ──────────────────────────────────────────────────


class KeywordExtractor:
    """Extract keywords from text using TF/IDF, n-grams, and tech term recognition."""

    TECH_PATTERNS = [
        re.compile(r"\b(JavaScript|TypeScript|Python|Java|Go|Rust|C\+\+|C#|Ruby|PHP|Kotlin|Swift)\b", re.IGNORECASE),
        re.compile(r"\b(React|Vue|Angular|Node\.js|Express|NestJS|Django|Flask|Spring|Svelte)\b", re.IGNORECASE),
        re.compile(r"\b(MySQL|PostgreSQL|MongoDB|Redis|Elasticsearch|Cassandra|SQLite|Oracle)\b", re.IGNORECASE),
        re.compile(r"\b(AWS|Azure|GCP|Kubernetes|Docker|Heroku|Vercel|Netlify)\b", re.IGNORECASE),
        re.compile(r"\b(REST|GraphQL|gRPC|WebSocket|JSON|XML|YAML)\b", re.IGNORECASE),
        re.compile(r"\b(API|SDK|CLI|IDE|CI/CD|TDD|BDD|DDD|OOP|FP|MVC|MVVM)\b", re.IGNORECASE),
    ]
    CN_TECH_TERMS = {"算法", "框架", "接口", "模块", "组件", "服务", "数据库", "缓存", "微服务", "容器", "部署", "监控", "日志", "认证", "授权", "加密", "索引", "查询"}

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall", "can", "need",
        "this", "that", "these", "those", "i", "you", "he", "she", "it",
        "we", "they", "what", "which", "who", "when", "where", "why", "how",
        "all", "each", "every", "both", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "also", "now", "here", "there", "then",
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    }

    def __init__(self, max_keywords: int = 50, use_ngrams: bool = True) -> None:
        self.max_keywords = max_keywords
        self.use_ngrams = use_ngrams

    def extract(self, text: str) -> list[Keyword]:
        kw_map: dict[str, Keyword] = {}
        for pattern in self.TECH_PATTERNS:
            for m in pattern.finditer(text):
                term = m.group(0).lower()
                if term in kw_map:
                    kw_map[term].frequency += 1
                    kw_map[term].score += 1.5
                else:
                    kw_map[term] = Keyword(text=term, type_="technical", frequency=1, score=1.5)
        for term in self.CN_TECH_TERMS:
            count = text.count(term)
            if count > 0:
                if term in kw_map:
                    kw_map[term].frequency += count
                    kw_map[term].score += count * 1.5
                else:
                    kw_map[term] = Keyword(text=term, type_="technical", frequency=count, score=count * 1.5)
        words = self._tokenize(text)
        freq = self._word_frequency(words)
        for word, count in freq.items():
            if word in kw_map:
                kw_map[word].frequency += count
                kw_map[word].score += count * 0.3
            elif len(word) >= 2 and word not in self.STOP_WORDS:
                kw_map[word] = Keyword(text=word, type_="word", frequency=count, score=float(count))
        sorted_kw = sorted(kw_map.values(), key=lambda k: k.score, reverse=True)
        return sorted_kw[: self.max_keywords]

    def _tokenize(self, text: str) -> list[str]:
        return [w for w in re.sub(r"[^\w\s一-鿿]", " ", text.lower()).split() if w]

    def _word_frequency(self, words: list[str]) -> dict[str, int]:
        freq: dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        return freq

    def calculate_tfidf(self, keywords: list[Keyword], documents: list[str]) -> list[Keyword]:
        if len(documents) <= 1:
            return keywords
        doc_count = len(documents)
        doc_freq: dict[str, int] = {}
        for doc in documents:
            for kw in {k.text for k in self.extract(doc)}:
                doc_freq[kw] = doc_freq.get(kw, 0) + 1
        results = []
        for kw in keywords:  # type: ignore[assignment]
            df = doc_freq.get(kw.text, 1)  # type: ignore[attr-defined]
            idf = math.log(doc_count / df)
            results.append(Keyword(text=kw.text, type_=kw.type_, frequency=kw.frequency, score=kw.frequency * idf, tfidf=kw.frequency * idf, idf=idf))  # type: ignore[attr-defined]
        results.sort(key=lambda k: k.score, reverse=True)
        return results

    def extract_from_sections(self, sections: list[dict[str, str]]) -> dict[str, list[Keyword]]:
        result: dict[str, list[Keyword]] = {}
        for sec in sections:
            text = f"{sec['title']} {sec['content']}"
            kws = self.extract(text)
            title_kws = self.extract(sec["title"])
            title_map = {tk.text for tk in title_kws}
            for kw in kws:
                if kw.text in title_map:
                    kw.score *= 1.5
            kws.sort(key=lambda k: k.score, reverse=True)
            result[sec["title"]] = kws
        return result


# ── AgentsMdIndexer ────────────────────────────────────────────────────


class AgentsMdIndexer:
    """Hybrid search indexer for AGENTS.md documents."""

    def __init__(self, enable_vector: bool = True, max_keywords_per_section: int = 20) -> None:
        self.parser = DocumentParser()
        self.extractor = KeywordExtractor()
        self.documents: dict[str, IndexedDocument] = {}
        self.enable_vector = enable_vector
        self.max_keywords_per_section = max_keywords_per_section

    async def index_document(self, doc_id: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        sections = self.parser.parse(content)
        section_keywords = self.extractor.extract_from_sections(
            [{"title": s.title, "content": s.content} for s in sections]
        )
        for section in sections:
            keywords = section_keywords.get(section.title, [])[: self.max_keywords_per_section]
            indexed = IndexedDocument(
                id=f"{doc_id}#{section.id}",
                title=section.title,
                content=section.content,
                section_id=section.id,
                keywords=keywords,
                importance=section.importance,
                metadata={
                    **(metadata or {}),
                    "document_id": doc_id,
                    "start_line": section.start_line,
                    "end_line": section.end_line,
                    "level": section.level,
                },
            )
            self.documents[indexed.id] = indexed

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_terms = query.lower().split()
        scored: list[tuple[float, IndexedDocument]] = []
        for doc in self.documents.values():
            score = 0.0
            text = f"{doc.title}\n{doc.content}".lower()
            for term in query_terms:
                if term in text:
                    score += 1.0
            for kw in doc.keywords:
                if kw.text in query.lower():
                    score += kw.score * 0.5
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[SearchResult] = []
        for score, doc in scored[:top_k]:
            content = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
            highlights = self._extract_highlights(doc.content, query)
            results.append(
                SearchResult(id=doc.id, title=doc.title, content=content, score=score, section_id=doc.section_id, highlights=highlights)
            )
        return results

    def _extract_highlights(self, content: str, query: str) -> list[str]:
        highlights: list[str] = []
        query_terms = query.lower().split()
        for line in content.split("\n"):
            if any(term in line.lower() for term in query_terms) and len(line.strip()) > 10:
                highlights.append(line.strip())
                if len(highlights) >= 3:
                    break
        return highlights

    def get_stats(self) -> dict[str, int]:
        doc_ids = {d.metadata.get("document_id", "") for d in self.documents.values()}
        return {
            "document_count": len(doc_ids),
            "section_count": len(self.documents),
            "total_chars": sum(len(d.content) for d in self.documents.values()),
        }

    def get_all_documents(self) -> list[IndexedDocument]:
        return list(self.documents.values())

    def get_document(self, doc_id: str) -> IndexedDocument | None:
        return self.documents.get(doc_id)


__all__ = [
    "Section", "CompressedIndex", "DocumentStats", "Keyword",
    "IndexedDocument", "SearchResult",
    "DocumentParser", "KeywordExtractor", "AgentsMdIndexer",
]
