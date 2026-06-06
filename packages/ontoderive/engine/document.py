from __future__ import annotations

#!/usr/bin/env python3
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Document ≡ Module
# 内涵 ≝ {Document}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Document)}
# 功能 ⊢ {Init_Document, Execute_Document, Validate_Document}
# =============================================================================

# ---
# Type: Module
# Status: ACTIVE
# Layer: L3
# ---
"""
Document Abstraction Layer - 文档抽象层

提供统一的文档接口，支持 Markdown、Python 等多种文档类型。

Design Principles:
- Protocol-based design (结构化子类型)
- Single responsibility (单一职责)
- Open/Closed principle (开闭原则)

Usage:
    doc = DocumentFactory.create(path)
    metadata = doc.metadata
    content = doc.content
    references = doc.extract_references()
"""


import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import yaml

# Event bus integration via kairon-lib-events
from kairon_events import BOSEvent, get_global_event_bus


class EventType(StrEnum):
    """Document event types published on the EventBus."""

    DOC_BEFORE_UPDATE = "doc.before_update"
    DOC_AFTER_UPDATE = "doc.after_update"


def get_event_bus() -> Any:
    """Return the global EventBus, or a dummy bus if unavailable."""
    if get_global_event_bus is None:
        return _DummyBus()
    bus = get_global_event_bus()
    if bus is None:
        return _DummyBus()
    return bus


class _DummyBus:
    """Silent no-op bus returned when the real EventBus is unavailable."""

    def publish(self, event: object) -> None:
        pass


class DocumentType(Enum):
    """文档类型枚举"""

    MARKDOWN = "markdown"
    PYTHON = "python"
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """统一的文档元数据模型

    所有类型的文档都共享此元数据结构。
    对于不支持的字段，使用默认值或 None。
    """

    path: Path
    doc_type: str = "Unknown"
    status: str = "UNKNOWN"
    version: str = "0.0.0"
    owner: str = "@Unassigned"
    authority: str = ""
    layer: str = ""
    updated: str = ""
    created: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)

    # 扩展字段（用于特定类型）
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_frontmatter(cls, path: Path) -> DocumentMetadata:
        """从 Markdown frontmatter 解析元数据"""
        content = path.read_text(encoding="utf-8")

        # 解析 frontmatter
        match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return cls(path=path)

        try:
            fm = yaml.safe_load(match.group(1))
            if not isinstance(fm, dict):
                return cls(path=path)
        except yaml.YAMLError:
            return cls(path=path)

        return cls(
            path=path,
            doc_type=fm.get("Type", "Unknown"),
            status=fm.get("Status", "UNKNOWN"),
            version=fm.get("Version", "0.0.0"),
            owner=fm.get("Owner", "@Unassigned"),
            authority=fm.get("Authority", ""),
            layer=str(fm.get("Layer", "")),
            updated=str(fm.get("Updated", fm.get("Created", "")) or ""),
            created=str(fm.get("Created", "") or ""),
            summary=str(fm.get("Summary", fm.get("description", "")) or ""),
            tags=fm.get("Tags", []),
            extra=fm,  # 保留原始数据
        )

    def to_frontmatter(self) -> str:
        """序列化为 YAML frontmatter"""
        import yaml

        data: dict[str, Any] = {
            "Type": self.doc_type,
            "Status": self.status,
            "Version": self.version,
            "Owner": self.owner,
            "Authority": self.authority,
            "Layer": self.layer,
            "Updated": self.updated or datetime.now().strftime("%Y-%m-%d"),
            "Summary": self.summary,
        }

        if self.tags:
            data["Tags"] = self.tags

        # 添加扩展字段
        for key, value in self.extra.items():
            if key not in data:
                data[key] = value

        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def is_valid(self) -> bool:
        """检查元数据是否有效"""
        required_fields = ["doc_type", "status", "version", "owner", "authority"]
        return all(getattr(self, f, None) for f in required_fields)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "path": str(self.path),
            "doc_type": self.doc_type,
            "status": self.status,
            "version": self.version,
            "owner": self.owner,
            "authority": self.authority,
            "layer": self.layer,
            "updated": self.updated,
            "summary": self.summary,
            "tags": self.tags,
            "is_valid": self.is_valid(),
        }


@dataclass
class Reference:
    """文档引用"""

    source: Path  # 引用来源
    target: str  # 引用目标（路径或标识符）
    ref_type: str  # 'link', 'import', 'citation', etc.
    context: str = ""  # 引用上下文
    line_number: int | None = None


class IDocument(Protocol):
    """文档协议 - 所有文档类型必须实现此接口

    这定义了文档的通用行为，使得不同类型的文档可以互换使用。
    """

    @property
    def path(self) -> Path:
        """文档路径"""
        ...

    @property
    def content(self) -> str:
        """文档内容"""
        ...

    @property
    def metadata(self) -> DocumentMetadata:
        """文档元数据"""
        ...

    @property
    def language(self) -> str:
        """文档语言 ('markdown', 'python', etc.)"""
        ...

    def extract_references(self) -> list[Reference]:
        """提取文档中的引用"""
        ...

    def update_metadata(self, metadata: DocumentMetadata) -> None:
        """更新文档元数据"""
        ...

    def save(self) -> None:
        """保存文档"""
        ...


UpdateEventNotifier = Callable[[str, Path], None]


def _publish_document_update_event(stage: str, path: Path) -> None:
    if BOSEvent is None:
        return

    event_type = {
        "before": EventType.DOC_BEFORE_UPDATE,
        "after": EventType.DOC_AFTER_UPDATE,
    }[stage]
    bus = get_event_bus()
    bus.publish(
        BOSEvent(
            event_type=event_type.value if hasattr(event_type, "value") else event_type,
            source="d-logos",
            payload={"doc_id": str(path), "path": str(path)},
            timestamp=time.time(),
            event_id=str(uuid4())[:8],
        )
    )


class BaseDocument(ABC):
    """文档基类 - 提供通用实现"""

    def __init__(
        self,
        path: Path,
        update_event_notifier: UpdateEventNotifier | None = None,
    ) -> None:
        self._path = path
        self._content: str | None = None
        self._metadata: DocumentMetadata | None = None
        self._update_event_notifier = update_event_notifier or _publish_document_update_event

    @property
    def path(self) -> Path:
        return self._path

    @property
    def content(self) -> str:
        """懒加载内容"""
        if self._content is None:
            self._content = self._path.read_text(encoding="utf-8")
        return self._content

    @property
    def metadata(self) -> DocumentMetadata:
        """懒加载元数据"""
        if self._metadata is None:
            self._metadata = self._load_metadata()
        return self._metadata

    @abstractmethod
    def _load_metadata(self) -> DocumentMetadata:
        """加载元数据（子类实现）"""
        pass

    @abstractmethod
    def extract_references(self) -> list[Reference]:
        """提取引用（子类实现）"""
        pass

    def update_metadata(self, metadata: DocumentMetadata) -> None:
        """更新元数据并重新保存，触发 BEFORE_DOC_UPDATE / AFTER_DOC_UPDATE 事件"""
        self._update_event_notifier("before", self._path)
        self._metadata = metadata
        self.save()
        self._update_event_notifier("after", self._path)

    def save(self) -> None:
        """保存文档"""
        if self._content is not None:
            self._path.write_text(self._content, encoding="utf-8")


class MarkdownDocument(BaseDocument):
    """Markdown 文档实现"""

    @property
    def language(self) -> str:
        return "markdown"

    def _load_metadata(self) -> DocumentMetadata:
        return DocumentMetadata.from_frontmatter(self.path)

    def extract_references(self) -> list[Reference]:
        """提取 Markdown 链接和引用"""
        references = []

        # Markdown 链接：[text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(link_pattern, self.content):
            text, url = match.groups()
            if not url.startswith("http"):  # 只处理相对链接
                references.append(
                    Reference(
                        source=self.path,
                        target=url,
                        ref_type="link",
                        context=text,
                        line_number=self.content[: match.start()].count("\n") + 1,
                    )
                )

        # Frontmatter 中的 Authority 引用
        if self.metadata.authority and not self.metadata.authority.startswith("http"):
            references.append(
                Reference(
                    source=self.path,
                    target=self.metadata.authority,
                    ref_type="authority",
                    context="Frontmatter Authority field",
                )
            )

        return references

    def save(self) -> None:
        """保存时重建 frontmatter"""
        if self._metadata:
            # 移除旧的 frontmatter
            content_without_fm = re.sub(r"^---\s*\n.*?\n---\s*\n", "", self.content, flags=re.DOTALL)

            # 添加新的 frontmatter
            self._content = f"---\n{self._metadata.to_frontmatter()}---\n\n{content_without_fm}"

        super().save()


class PythonDocument(BaseDocument):
    """Python 文档实现（简化版，后续可扩展）"""

    @property
    def language(self) -> str:
        return "python"

    def _load_metadata(self) -> DocumentMetadata:
        """从 Python 文件头注释或 docstring 提取元数据"""
        # 尝试从文件头注释提取
        match = re.search(r"^#\s*---\s*\n(.*?)#\s*---\s*\n", self.content, re.DOTALL)
        if match:
            try:
                # 移除行首的 #
                yaml_text = re.sub(r"^#\s*", "", match.group(1), flags=re.MULTILINE)
                fm = yaml.safe_load(yaml_text)
                if isinstance(fm, dict):
                    return DocumentMetadata(
                        path=self.path,
                        doc_type=fm.get("Type", "Python Module"),
                        status=fm.get("Status", "ACTIVE"),
                        version=fm.get("Version", "0.0.0"),
                        owner=fm.get("Owner", "@Unassigned"),
                        authority=fm.get("Authority", ""),
                        extra=fm,
                    )
            except yaml.YAMLError:
                pass

        # 默认元数据
        return DocumentMetadata(path=self.path, doc_type="Python Module", status="ACTIVE")

    def extract_references(self) -> list[Reference]:
        """提取 Python imports 和 docstring 引用"""
        references = []

        # 提取 import 语句
        import_pattern = r"^(?:from\s+(\S+)\s+)?import\s+(.+)$"
        for match in re.finditer(import_pattern, self.content, re.MULTILINE):
            module, names = match.groups()
            if module:
                references.append(
                    Reference(
                        source=self.path,
                        target=module.replace(".", "/"),
                        ref_type="import",
                        context=f"import {names}" if names else "",
                        line_number=self.content[: match.start()].count("\n") + 1,
                    )
                )

        return references


class DocumentFactory:
    """文档工厂 - 根据文件扩展名创建合适的文档对象"""

    _registry: dict[str, type[IDocument]] = {
        ".md": MarkdownDocument,
        ".markdown": MarkdownDocument,
        ".py": PythonDocument,
    }

    @classmethod
    def register(cls, extension: str, doc_class: type[IDocument]) -> None:
        """注册新的文档类型"""
        cls._registry[extension.lower()] = doc_class

    @classmethod
    def create(cls, path: Path) -> IDocument:
        """根据路径创建文档对象"""
        ext = path.suffix.lower()
        doc_class = cls._registry.get(ext, MarkdownDocument)  # 默认使用 Markdown
        return doc_class(path)

    @classmethod
    def get_document_type(cls, path: Path) -> DocumentType:
        """获取文档类型"""
        ext = path.suffix.lower()
        if ext in [".md", ".markdown"]:
            return DocumentType.MARKDOWN
        elif ext == ".py":
            return DocumentType.PYTHON
        else:
            return DocumentType.UNKNOWN


# 便捷函数
def open_document(path: str | Path) -> IDocument:
    """打开文档的便捷函数"""
    return DocumentFactory.create(Path(path))


if __name__ == "__main__":
    # 使用示例
    import sys

    if len(sys.argv) < 2:
        print("Usage: python document.py <file_path>")
        sys.exit(1)

    path = Path(sys.argv[1])
    doc = open_document(path)

    print(f"Path: {doc.path}")
    print(f"Language: {doc.language}")
    print(f"Metadata: {doc.metadata.to_dict()}")
    print(f"References: {len(doc.extract_references())} found")
