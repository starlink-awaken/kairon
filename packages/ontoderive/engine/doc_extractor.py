from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_log = logging.getLogger(__name__)


"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for doc_extractor.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Doc Extractor ≡ Module
# 内涵 ≝ {Doc, Extractor}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, DocExtractor)}
# 功能 ⊢ {Doc_Extractor, Init_Doc, Validate_Extractor}
# =============================================================================


"""文档声明提取器 (DocStatementExtractor)

从 Markdown 文档中提取架构声明:
- 组件声明 (类、接口、模块)
- 接口声明 (方法签名、参数、返回值)
- 协议声明 (触发器、状态机、约束)
- 配置声明 (YAML frontmatter、schema)

输出：结构化 AST (Abstract Syntax Tree)
"""


try:
    import yaml
except ImportError:
    yaml = None


class DeclarationType(Enum):
    """声明类型"""

    COMPONENT = "component"  # 组件（类、模块）
    INTERFACE = "interface"  # 接口（方法签名）
    PROTOCOL = "protocol"  # 协议（触发器、状态机）
    CONFIG = "config"  # 配置（YAML schema）
    CONSTRAINT = "constraint"  # 约束（规则、限制）
    EVENT = "event"  # 事件（触发条件）


class DeclarationStatus(Enum):
    """声明状态"""

    DEFINED = "defined"  # 已定义
    DEPRECATED = "deprecated"  # 已弃用
    PROPOSED = "proposed"  # 提议中


@dataclass
class Declaration:
    """架构声明"""

    # 基本信息
    id: str  # 唯一标识符 (e.g., "SymphonyStageManager")
    type: DeclarationType  # 声明类型
    status: DeclarationStatus  # 状态
    source_file: Path  # 源文件路径
    line_number: int  # 行号

    # 内容信息
    name: str  # 名称
    description: str  # 描述
    parent: str | None = None  # 父级声明 (用于嵌套结构)

    # 接口信息 (针对 interface 类型)
    parameters: list[dict] = field(default_factory=list)
    return_type: str | None = None
    exceptions: list[str] = field(default_factory=list)

    # 协议信息 (针对 protocol 类型)
    triggers: list[dict] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)

    # 约束信息 (针对 constraint 类型)
    constraints: list[str] = field(default_factory=list)

    # 元数据
    tags: list[str] = field(default_factory=list)
    version: str | None = None
    created: str | None = None
    updated: str | None = None

    # 原始内容
    raw_content: str = ""
    context_before: str = ""  # 上下文（用于定位）
    context_after: str = ""


@dataclass
class DocumentAST:
    """文档 AST"""

    source_file: Path
    declarations: list[Declaration]
    frontmatter: dict
    imports: list[str]
    references: list[str]  # 引用的其他文档


class DocStatementExtractor:
    """文档声明提取器"""

    def __init__(self) -> None:
        self.declarations: list[Declaration] = []
        self.documents: list[DocumentAST] = []

    def extract_from_directory(self, docs_dir: Path) -> list[DocumentAST]:
        """从目录提取所有文档声明"""
        _log.info("📄 扫描文档目录：{docs_dir}")

        for md_file in docs_dir.rglob("*.md"):
            if self._should_skip(md_file):
                continue
            ast = self.extract_from_file(md_file)
            self.documents.append(ast)

        _log.info("✅ 扫描完成：{len(self.documents)} 个文档")
        return self.documents

    def _should_skip(self, path: Path) -> bool:
        """判断是否跳过文件"""
        skip_patterns = [
            "node_modules",
            ".git",
            ".trash",
            "archive",
            "backup",
            ".venv",
            "venv",
            "__pycache__",
        ]
        path_str = str(path).lower()
        return any(pattern in path_str for pattern in skip_patterns)

    def extract_from_file(self, file_path: Path) -> DocumentAST:
        """从单个文件提取声明"""
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        # 提取 frontmatter
        frontmatter = self._extract_frontmatter(content)

        # 提取各类声明
        declarations = []

        # 1. 提取类/组件声明
        declarations.extend(self._extract_class_declarations(content, lines, file_path))

        # 2. 提取接口声明
        declarations.extend(self._extract_interface_declarations(content, lines, file_path))

        # 3. 提取协议声明
        declarations.extend(self._extract_protocol_declarations(content, lines, file_path))

        # 4. 提取配置声明
        declarations.extend(self._extract_config_declarations(content, lines, file_path))

        # 5. 提取约束声明
        declarations.extend(self._extract_constraint_declarations(content, lines, file_path))

        # 提取引用
        references = self._extract_references(content)

        return DocumentAST(
            source_file=file_path,
            declarations=declarations,
            frontmatter=frontmatter,
            imports=[],  # Markdown 没有 import
            references=references,
        )

    def _extract_frontmatter(self, content: str) -> dict:
        """提取 YAML frontmatter"""
        if yaml is None:
            return {}

        patterns = [
            r"^---\s*\n(.*?)\n---\s*\n",
            r"^---\s*\n(.*?)\n---",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
            if match:
                try:
                    frontmatter_str = match.group(1)
                    return yaml.safe_load(frontmatter_str) or {}
                except (yaml.YAMLError, ValueError):
                    pass
        return {}

    def _extract_class_declarations(self, content: str, lines: list[str], source_file: Path) -> list[Declaration]:
        """提取类/组件声明"""
        declarations = []

        # 匹配 Markdown 中的类定义模式
        patterns = [
            # Markdown 标题形式：## SymphonyStageManager
            (r"^#{2,3}\s+([A-Z][A-Za-z0-9_]+)\s*$", "heading"),
            # 代码块中的类定义
            (r"```python\s*\nclass\s+([A-Z][A-Za-z0-9_]+)", "code"),
        ]

        for i, line in enumerate(lines):
            for pattern, _source_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    class_name = match.group(1)
                    decl = Declaration(
                        id=class_name,
                        type=DeclarationType.COMPONENT,
                        status=DeclarationStatus.DEFINED,
                        source_file=source_file,
                        line_number=i + 1,
                        name=class_name,
                        description=self._extract_description(lines, i),
                        raw_content=line,
                        context_before="\n".join(lines[max(0, i - 3) : i]),
                        context_after="\n".join(lines[i + 1 : min(len(lines), i + 10)]),
                    )
                    declarations.append(decl)
                    break

        return declarations

    def _extract_interface_declarations(self, content: str, lines: list[str], source_file: Path) -> list[Declaration]:
        """提取接口声明"""
        declarations = []

        # 匹配方法签名模式
        # - method_name(param1: type, param2: type) -> return_type
        pattern = r"[-*]\s*`?([a-z_][a-z0-9_]*)\s*\(([^)]*)\)\s*(?:->\s*([^\n]+))?`?"

        for i, line in enumerate(lines):
            matches = re.finditer(pattern, line)
            for match in matches:
                method_name = match.group(1)
                params_str = match.group(2)
                return_type = match.group(3)

                # 解析参数
                parameters = self._parse_parameters(params_str)

                decl = Declaration(
                    id=method_name,
                    type=DeclarationType.INTERFACE,
                    status=DeclarationStatus.DEFINED,
                    source_file=source_file,
                    line_number=i + 1,
                    name=method_name,
                    description=self._extract_description(lines, i),
                    parameters=parameters,
                    return_type=return_type.strip() if return_type else None,
                    raw_content=line,
                )
                declarations.append(decl)

        return declarations

    def _extract_protocol_declarations(self, content: str, lines: list[str], source_file: Path) -> list[Declaration]:
        """提取协议声明（触发器、状态机）"""
        declarations = []

        # 匹配触发器表格
        # | 触发器 | 条件 | 动作 |
        trigger_pattern = r"\|\s*([A-Z_]+)\s*\|\s*([^|]+)\|\s*([^|]+)\|"

        in_trigger_section = False
        current_triggers = []
        trigger_start_line = -1

        for i, line in enumerate(lines):
            if "触发器" in line or "trigger" in line.lower():
                in_trigger_section = True
                trigger_start_line = i
                continue

            if in_trigger_section:
                match = re.search(trigger_pattern, line)
                if match:
                    trigger_name = match.group(1)
                    trigger_condition = match.group(2).strip()
                    trigger_action = match.group(3).strip()

                    current_triggers.append(
                        {
                            "name": trigger_name,
                            "condition": trigger_condition,
                            "action": trigger_action,
                        }
                    )
                elif line.strip().startswith("|---"):
                    # 表格分隔线，继续
                    pass
                elif line.strip() and not line.strip().startswith("|"):
                    # 表格结束
                    if current_triggers:
                        decl = Declaration(
                            id=f"protocol_triggers_{trigger_start_line}",
                            type=DeclarationType.PROTOCOL,
                            status=DeclarationStatus.DEFINED,
                            source_file=source_file,
                            line_number=trigger_start_line,
                            name="Protocol Triggers",
                            description="协议触发器定义",
                            triggers=current_triggers,
                            raw_content="\n".join(lines[trigger_start_line : i + 1]),
                        )
                        declarations.append(decl)
                        current_triggers = []
                    in_trigger_section = False

        return declarations

    def _extract_config_declarations(self, content: str, lines: list[str], source_file: Path) -> list[Declaration]:
        """提取配置声明（YAML schema）"""
        declarations = []

        if yaml is None:
            return declarations

        # 匹配 YAML 代码块
        yaml_pattern = r"```(?:ya?ml)\s*\n(^[^-].*?\n)```"

        for match in re.finditer(yaml_pattern, content, re.MULTILINE | re.DOTALL):
            yaml_content = match.group(1)
            try:
                config_data = yaml.safe_load(yaml_content)
                if config_data and isinstance(config_data, dict):
                    decl = Declaration(
                        id=f"config_{len(declarations)}",
                        type=DeclarationType.CONFIG,
                        status=DeclarationStatus.DEFINED,
                        source_file=source_file,
                        line_number=content[: match.start()].count("\n") + 1,
                        name="Configuration Schema",
                        description="配置 Schema 定义",
                        constraints=[str(k) for k in config_data.keys()],
                        raw_content=yaml_content,
                    )
                    declarations.append(decl)
            except (yaml.YAMLError, KeyError, TypeError, ValueError):
                pass

        return declarations

    def _extract_constraint_declarations(self, content: str, lines: list[str], source_file: Path) -> list[Declaration]:
        """提取约束声明"""
        declarations = []

        # 匹配约束模式
        # - 必须...
        # - 禁止...
        # - 应该...
        constraint_markers = ["必须", "禁止", "应该", "MUST", "MUST NOT", "SHOULD", "will", "shall"]

        current_constraints = []
        constraint_start_line = -1

        for i, line in enumerate(lines):
            for marker in constraint_markers:
                if marker in line:
                    if constraint_start_line == -1:
                        constraint_start_line = i
                    current_constraints.append(line.strip())
                    break

        if current_constraints:
            decl = Declaration(
                id=f"constraints_{constraint_start_line}",
                type=DeclarationType.CONSTRAINT,
                status=DeclarationStatus.DEFINED,
                source_file=source_file,
                line_number=constraint_start_line + 1,
                name="Constraints",
                description="约束条件",
                constraints=current_constraints,
                raw_content="\n".join(current_constraints),
            )
            declarations.append(decl)

        return declarations

    def _extract_references(self, content: str) -> list[str]:
        """提取文档引用"""
        references = []

        # 匹配 Markdown 链接
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(link_pattern, content):
            match.group(1)
            link_url = match.group(2)
            if link_url.endswith(".md") or link_url.startswith("./"):
                references.append(link_url)

        return references

    def _extract_description(self, lines: list[str], current_line: int) -> str:
        """从上下文提取描述"""
        # 向前查找描述（最多 3 行）
        description_lines = []
        for i in range(current_line - 1, max(current_line - 4, -1), -1):
            line = lines[i].strip()
            if line and not line.startswith("#"):
                description_lines.insert(0, line)
            elif line.startswith("#"):
                break

        return " ".join(description_lines[:2])

    def _parse_parameters(self, params_str: str) -> list[dict]:
        """解析参数字符串"""
        if not params_str.strip():
            return []

        parameters = []
        # 简单分割（假设没有复杂的嵌套类型）
        for param in params_str.split(","):
            param = param.strip()
            if ":" in param:
                name, type_hint = param.split(":", 1)
                parameters.append(
                    {
                        "name": name.strip(),
                        "type": type_hint.strip(),
                    }
                )
            elif param:
                parameters.append({"name": param.strip()})

        return parameters

    def export_ast(self, output_path: Path) -> None:
        """导出 AST 到 JSON"""
        import json
        from datetime import date, datetime

        def serialize_value(val: object) -> object:
            """序列化特殊类型"""
            if isinstance(val, (datetime, date)):
                return val.isoformat()
            elif isinstance(val, Path):
                return str(val)
            return val

        def serialize_dict(d: object) -> object:
            """序列化字典"""
            if not isinstance(d, dict):
                return d
            return {k: serialize_value(v) for k, v in d.items()}

        data = {
            "documents": [
                {
                    "source_file": str(doc.source_file),
                    "frontmatter": serialize_dict(doc.frontmatter),
                    "declarations": [
                        {
                            "id": d.id,
                            "type": d.type.value,
                            "status": d.status.value,
                            "name": d.name,
                            "description": d.description,
                            "line_number": d.line_number,
                            "parameters": d.parameters,
                            "return_type": d.return_type,
                            "triggers": d.triggers,
                            "constraints": d.constraints,
                            "raw_content": d.raw_content[:500] if d.raw_content else "",
                        }
                        for d in doc.declarations
                    ],
                    "references": doc.references,
                }
                for doc in self.documents
            ]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        _log.info("✅ AST 已导出：{output_path}")
