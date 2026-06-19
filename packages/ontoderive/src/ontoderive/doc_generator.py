from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import ast
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for doc_generator.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Doc Generator ≡ Generator
# 内涵 ≝ {Doc, Generator}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, DocGenerator)}
# 功能 ⊢ {Doc_Generator, Init_Doc, Validate_Generator}
# =============================================================================


"""文档生成器 (DocGenerator)

基于代码 AST 自动生成文档模板，不调用外部 API。

功能:
- 使用 Python ast 模块解析代码
- 提取函数、类、参数、返回值信息
- 复用 D-Logos archetypes 模板
- 生成 Markdown 格式文档

Usage:
    from D_Logos.organs import DocGenerator

    generator = DocGenerator()
    # 解析单个文件
    entities = generator.parse_file("path/to/module.py")
    # 生成 API 参考文档
    doc = generator.generate_api_reference(entities)
    # 生成代码结构文档
    doc = generator.generate_code_structure(entities)
"""

_log = logging.getLogger(__name__)


@dataclass
class ParsedEntity:
    """解析后的代码实体"""

    name: str
    type: str  # "class", "function", "method"
    lineno: int
    docstring: str | None = None
    parameters: list[dict] = field(default_factory=list)
    returns: str | None = None
    decorators: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    methods: list[ParsedEntity] = field(default_factory=list)


@dataclass
class ParsedModule:
    """解析后的模块"""

    path: Path
    name: str
    imports: list[str] = field(default_factory=list)
    from_imports: list[dict] = field(default_factory=list)
    classes: list[ParsedEntity] = field(default_factory=list)
    functions: list[ParsedEntity] = field(default_factory=list)


class DocGenerator:
    """文档生成器

    基于 Python AST 生成文档模板。
    """

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()

    def parse_file(self, file_path: str | Path) -> ParsedModule:
        """解析单个 Python 文件

        Args:
            file_path: Python 文件路径

        Returns:
            ParsedModule: 解析后的模块
        """
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8")

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            raise ValueError(f"Syntax error in {file_path}: {e}") from e

        module = ParsedModule(
            path=file_path,
            name=file_path.stem,
        )

        # 提取导入
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    module.from_imports.append(
                        {
                            "module": node.module or "",
                            "name": alias.name,
                            "asname": alias.asname,
                        }
                    )

        # 提取类和函数（顶层）
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                entity = self._parse_class(node)
                module.classes.append(entity)
            elif isinstance(node, ast.FunctionDef):
                entity = self._parse_function(node)
                module.functions.append(entity)

        return module

    def parse_directory(self, dir_path: str | Path) -> list[ParsedModule]:
        """解析目录下所有 Python 文件

        Args:
            dir_path: 目录路径

        Returns:
            list[ParsedModule]: 解析后的模块列表
        """
        dir_path = Path(dir_path)
        modules = []

        for root, _, files in os.walk(dir_path):
            # 跳过特殊目录
            if any(skip in root for skip in ["__pycache__", ".git", ".venv", "venv", "node_modules"]):
                continue

            for file in files:
                if file.endswith(".py") and not file.startswith("test_"):
                    file_path = Path(root) / file
                    try:
                        module = self.parse_file(file_path)
                        modules.append(module)
                    except (SyntaxError, OSError, ValueError):
                        # 跳过无法解析的文件
                        _log.info("Warning: Failed to parse {file_path}: {e}")
                        continue

        return modules

    def _parse_class(self, node: ast.ClassDef) -> ParsedEntity:
        """解析类定义"""
        entity = ParsedEntity(
            name=node.name,
            type="class",
            lineno=node.lineno,
            docstring=ast.get_docstring(node),
            bases=[self._get_name(base) for base in node.bases],
            decorators=[self._get_name(d) for d in node.decorator_list],
        )

        # 提取方法
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method = self._parse_function(item)
                method.type = "method"
                entity.methods.append(method)

        return entity

    def _parse_function(self, node: ast.FunctionDef) -> ParsedEntity:
        """解析函数定义"""
        entity = ParsedEntity(
            name=node.name,
            type="function" if hasattr(node, "parent") else "function",
            lineno=node.lineno,
            docstring=ast.get_docstring(node),
            returns=self._get_return_annotation(node.returns),
            decorators=[self._get_name(d) for d in node.decorator_list],
            parameters=self._get_parameters(node.args),
        )
        return entity

    def _get_parameters(self, args: ast.arguments) -> list[dict]:
        """提取参数列表"""
        parameters = []

        # 位置参数
        for arg in args.args:
            parameters.append(
                {
                    "name": arg.arg,
                    "type": self._get_type_annotation(arg.annotation),
                    "default": None,
                }
            )

        # 默认值
        defaults = list(args.defaults) if args.defaults else []
        for i, default in enumerate(defaults):
            param_idx = len(parameters) - len(defaults) + i
            if param_idx >= 0:
                parameters[param_idx]["default"] = ast.unparse(default)

        # *args 和 **kwargs
        if args.vararg:
            parameters.append(
                {
                    "name": f"*{args.vararg.arg}",
                    "type": self._get_type_annotation(args.vararg.annotation),
                    "default": None,
                }
            )

        if args.kwarg:
            parameters.append(
                {
                    "name": f"**{args.kwarg.arg}",
                    "type": self._get_type_annotation(args.kwarg.annotation),
                    "default": None,
                }
            )

        return parameters

    def _get_name(self, node: ast.AST | None) -> str:
        """获取节点名称"""
        if node is None:
            return ""

        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        else:
            return ast.unparse(node)

    def _get_type_annotation(self, node: ast.AST | None) -> str | None:
        """获取类型注解"""
        if node is None:
            return None

        try:
            return ast.unparse(node)
        except (ValueError, AttributeError):
            return None

    def _get_return_annotation(self, node: ast.AST | None) -> str | None:
        """获取返回类型注解"""
        return self._get_type_annotation(node)

    def generate_api_reference(self, modules: list[ParsedModule]) -> str:
        """生成 API 参考文档

        Args:
            modules: 解析后的模块列表

        Returns:
            str: Markdown 格式的 API 参考文档
        """
        today = date.today().isoformat()
        lines = [
            "---",
            "Type: Reference",
            "Status: DRAFT",
            "Layer: L3",
            "Summary: Auto-generated API reference document",
            f"Updated: {today}",
            "---",
            "",
            "# API Reference - API 参考文档",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "**状态**: 草稿（需人工审核）",
            "",
            "---",
            "",
            "## 概述",
            "",
            f"本文档由 DocGenerator 自动生成，共解析 {len(modules)} 个模块。",
            "",
            "---",
            "",
            "## 模块列表",
            "",
            "| 模块 | 路径 | 类数量 | 函数数量 |",
            "|-----|------|--------|---------|",
        ]

        for module in modules:
            lines.append(f"| `{module.name}` | `{module.path}` | {len(module.classes)} | {len(module.functions)} |")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 详细 API")

        for module in modules:
            lines.append("")
            lines.append(f"### 模块: `{module.name}`")
            lines.append("")
            lines.append(f"**路径**: `{module.path}`")
            lines.append("")

            # 导入
            if module.imports or module.from_imports:
                lines.append("**导入**:")
                for imp_mod in module.imports:
                    lines.append(f"- `import {imp_mod}`")
                for imp_from in module.from_imports:
                    if imp_from["asname"]:
                        lines.append(f"- `from {imp_from['module']} import {imp_from['name']} as {imp_from['asname']}`")
                    else:
                        lines.append(f"- `from {imp_from['module']} import {imp_from['name']}`")
                lines.append("")

            # 类
            for cls in module.classes:
                lines.append(f"#### 类: `{cls.name}`")
                lines.append("")

                if cls.docstring:
                    lines.append(f"{cls.docstring}")
                    lines.append("")

                if cls.bases:
                    lines.append(f"**继承**: `{', '.join(cls.bases)}`")
                    lines.append("")

                # 方法表
                if cls.methods:
                    lines.append("| 方法 | 签名 | 说明 |")
                    lines.append("|------|------|------|")
                    for method in cls.methods:
                        sig = self._format_signature(method)
                        desc = method.docstring or ""
                        lines.append(f"| `{method.name}` | `{sig}` | {desc} |")
                    lines.append("")

            # 顶层函数
            for func in module.functions:
                lines.append(f"#### 函数: `{func.name}`")
                lines.append("")

                if func.docstring:
                    lines.append(f"{func.docstring}")
                    lines.append("")

                sig = self._format_signature(func)
                lines.append(f"**签名**: `{sig}`")
                lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("## 使用示例")
        lines.append("")
        lines.append("```python")
        for module in modules[:3]:  # 前3个模块
            if module.classes:
                cls = module.classes[0]
                lines.append(f"# 使用 {cls.name} 类")
                if cls.methods:
                    method = cls.methods[0]
                    lines.append(f"obj = {cls.name}()")
                    lines.append(f"result = obj.{method.name}()")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 注意事项")
        lines.append("")
        lines.append("- 本文档由 DocGenerator 自动生成")
        lines.append("- 内容仅供初步参考，务必人工审核")
        lines.append("- 类型注解基于 Python 3.10+ 语法")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*Generated by DocGenerator*")

        return "\n".join(lines)

    def generate_code_structure(self, modules: list[ParsedModule]) -> str:
        """生成代码结构文档

        Args:
            modules: 解析后的模块列表

        Returns:
            str: Markdown 格式的代码结构文档
        """
        today = date.today().isoformat()
        lines = [
            "---",
            "Type: Reference",
            "Status: DRAFT",
            "Layer: L3",
            "Summary: Auto-generated code structure document",
            f"Updated: {today}",
            "---",
            "",
            "# Code Structure - 代码结构",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "**状态**: 草稿（需人工审核）",
            "",
            "---",
            "",
            "## 概述",
            "",
            "本文档由 DocGenerator 自动生成，展示代码结构概览。",
            "",
            "---",
            "",
            "## 文件树",
            "",
            "```",
        ]

        # 生成文件树
        tree = self._build_tree(modules)
        lines.extend(tree)

        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 模块详情")
        lines.append("")

        for module in modules:
            lines.append(f"### `{module.name}`")
            lines.append("")
            lines.append(f"路径: `{module.path}`")
            lines.append("")

            if module.classes:
                lines.append("**类**:")
                for cls in module.classes:
                    methods = [m.name for m in cls.methods]
                    lines.append(f"- `{cls.name}`" + (f" ({', '.join(methods)})" if methods else ""))
                lines.append("")

            if module.functions:
                lines.append("**函数**:")
                for func in module.functions:
                    lines.append(f"- `{func.name}()`")
                lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Generated by DocGenerator*")

        return "\n".join(lines)

    def _build_tree(self, modules: list[ParsedModule]) -> list[str]:
        """构建文件树"""
        tree_lines = []

        for module in modules:
            tree_lines.append(f"📁 {module.path.name}")
            tree_lines.append(f"  ├── 📄 {module.name}.py")

            if module.classes:
                for i, cls in enumerate(module.classes):
                    prefix = "  └── " if i == len(module.classes) - 1 and not module.functions else "  ├── "
                    tree_lines.append(f"{prefix}📦 {cls.name}")

                    for j, method in enumerate(cls.methods):
                        method_prefix = "      └── " if j == len(cls.methods) - 1 else "      ├── "
                        tree_lines.append(f"{method_prefix}⚡ {method.name}()")

            if module.functions:
                for i, func in enumerate(module.functions):
                    prefix = "  └── " if i == len(module.functions) - 1 else "  ├── "
                    tree_lines.append(f"{prefix}⚡ {func.name}()")

            tree_lines.append("")

        return tree_lines

    def _format_signature(self, entity: ParsedEntity) -> str:
        """格式化函数/方法签名"""
        params = []
        for param in entity.parameters:
            name = param["name"]
            ptype = param.get("type", "")
            default = param.get("default")

            if default:
                params.append(f"{name}={default}")
            elif ptype:
                params.append(f"{name}: {ptype}")
            else:
                params.append(name)

        sig = f"{entity.name}({', '.join(params)})"

        if entity.returns:
            sig += f" -> {entity.returns}"

        return sig

    def generate_document(
        self,
        source: str | Path | list[ParsedModule],
        template: str = "api_reference",
    ) -> str:
        """生成文档

        Args:
            source: Python 文件路径、目录路径，或已解析的模块列表
            template: 模板类型 ("api_reference", "code_structure")

        Returns:
            str: Markdown 格式的文档
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.is_file():
                modules = [self.parse_file(path)]
            else:
                modules = self.parse_directory(path)
        elif isinstance(source, list):
            modules = source
        else:
            raise ValueError("source must be a file path, directory path, or list of ParsedModule")

        if template == "api_reference":
            return self.generate_api_reference(modules)
        elif template == "code_structure":
            return self.generate_code_structure(modules)
        else:
            raise ValueError(f"Unknown template: {template}")

    # ------------------------------------------------------------------
    # Doc Governance: Mechanism 4 — Updated auto-bump
    # ------------------------------------------------------------------

    # Regex matching the Updated: frontmatter line (used for hashing & bumping)
    _UPDATED_RE = re.compile(r"^(Updated:\s*)(.+)$", re.MULTILINE)
    # Strip Updated line before hashing to avoid false-positive stale signals
    _UPDATED_STRIP_RE = re.compile(r"^Updated:.*$", re.MULTILINE)

    def bump_updated(self, doc_path: Path) -> bool:
        """Update the ``Updated:`` frontmatter field to today's ISO date if content changed.

        The check is hash-based: the SHA-256 of the file content (with the
        ``Updated:`` line stripped) is compared against the previous value
        stored in a sidecar ``.hash`` file next to the document.  If the hash
        differs the ``Updated`` field is rewritten in-place and the sidecar is
        updated.

        Returns:
            ``True`` when the file was modified (Updated bumped).
            ``False`` when the content is unchanged or the file does not exist.
        """
        doc_path = Path(doc_path)
        if not doc_path.exists():
            return False

        content = doc_path.read_text(encoding="utf-8")
        normalised = self._UPDATED_STRIP_RE.sub("Updated: <stripped>", content)
        current_hash = hashlib.sha256(normalised.encode("utf-8")).hexdigest()

        # Sidecar hash file lives alongside the doc as .{stem}.hash
        hash_file = doc_path.parent / f".{doc_path.stem}.hash"
        if hash_file.exists():
            previous_hash = hash_file.read_text(encoding="utf-8").strip()
            if previous_hash == current_hash:
                return False  # Nothing changed

        # Content changed (or first run) — bump Updated
        today_str = date.today().isoformat()

        if self._UPDATED_RE.search(content):
            new_content = self._UPDATED_RE.sub(rf"\g<1>{today_str}", content, count=1)
        else:
            # Inject Updated after the closing --- of frontmatter if possible
            lines = content.splitlines(keepends=True)
            inserted = False
            new_lines = []
            in_fm = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if i == 0 and stripped == "---":
                    in_fm = True
                    new_lines.append(line)
                    continue
                if in_fm and stripped == "---":
                    # Insert before closing delimiter
                    new_lines.append(f"Updated: {today_str}\n")
                    new_lines.append(line)
                    in_fm = False
                    inserted = True
                    continue
                new_lines.append(line)
            if not inserted:
                new_lines.append(f"\nUpdated: {today_str}\n")
            new_content = "".join(new_lines)

        doc_path.write_text(new_content, encoding="utf-8")
        hash_file.write_text(current_hash, encoding="utf-8")
        _log.debug("Bumped Updated for %s → %s", doc_path.name, today_str)
        return True

    # ------------------------------------------------------------------
    # End Mechanism 4
    # ------------------------------------------------------------------


# 便捷函数
def generate_doc(source: str | Path, template: str = "api_reference") -> str:
    """便捷函数：生成文档

    Args:
        source: Python 文件或目录路径
        template: 模板类型

    Returns:
        str: Markdown 文档
    """
    generator = DocGenerator()
    return generator.generate_document(source, template)
