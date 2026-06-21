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
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for impl_scanner.py'
Tags:
- auto-metadata
Authority: organs/D-Logos/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Impl Scanner ≡ Scanner
# 内涵 ≝ {Impl, Scanner}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, ImplScanner)}
# 功能 ⊢ {Impl_Scanner, Init_Impl, Validate_Scanner}
# =============================================================================


"""代码实现扫描器 (ImplementationScanner)

扫描代码库验证实现:
- 识别模块、包
- 识别类、函数
- 生成实现清单
- 构建导入图

输出：实现清单 (Implementation Manifest)
"""

_log = logging.getLogger(__name__)


@dataclass
class CodeEntity:
    """代码实体"""

    # 基本信息
    id: str  # 唯一标识符
    entity_type: str  # 实体类型 (module, class, function, method)
    name: str  # 名称
    qualified_name: str  # 限定名 (e.g., "module.Class.method")

    # 位置信息
    source_file: Path  # 源文件
    line_number: int  # 行号
    end_line: int | None = None  # 结束行

    # 签名信息
    parameters: list[dict] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)

    # 文档字符串
    docstring: str | None = None

    # 依赖信息
    imports: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    # 状态标记
    is_async: bool = False
    is_abstract: bool = False
    is_private: bool = False
    status: str = "active"  # active, deprecated, stub


@dataclass
class ImplementationManifest:
    """实现清单"""

    source_root: Path
    modules: list[CodeEntity]
    classes: list[CodeEntity]
    functions: list[CodeEntity]
    methods: list[CodeEntity]
    imports_map: dict[str, list[str]]  # module -> imports


class ImplementationScanner:
    """代码实现扫描器"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.entities: list[CodeEntity] = []
        self.manifest: ImplementationManifest | None = None

    def scan(
        self, include_patterns: list[str] | None = None, exclude_patterns: list[str] | None = None
    ) -> ImplementationManifest:
        """扫描代码库"""
        _log.info("🔍 扫描代码库：{self.root}")

        if include_patterns is None:
            include_patterns = ["**/*.py"]
        if exclude_patterns is None:
            exclude_patterns = [
                "**/__pycache__/**",
                "**/.git/**",
                "**/tests/**",
                "**/test_*.py",
                "**/*_test.py",
                "**/node_modules/**",
                "**/*.pyc",
                "**/.venv/**",
                "**/venv/**",
                "**/backup/**",
                "**/.backup/**",
                "**/.trash/**",
                "**/archive/**",
            ]

        # 收集 Python 文件
        python_files = []
        for pattern in include_patterns:
            for file_path in self.root.glob(pattern):
                if not any(file_path.match(exc) for exc in exclude_patterns):
                    python_files.append(file_path)

        _log.info("  找到 {len(python_files)} 个 Python 文件")

        # 扫描每个文件
        modules = []
        classes = []
        functions = []
        methods = []
        imports_map: dict[str, list[str]] = {}

        for file_path in python_files:
            entities = self._scan_file(file_path)

            for entity in entities:
                if entity.entity_type == "module":
                    modules.append(entity)
                elif entity.entity_type == "class":
                    classes.append(entity)
                elif entity.entity_type == "function":
                    functions.append(entity)
                elif entity.entity_type == "method":
                    methods.append(entity)

                # 构建导入图
                if entity.imports:
                    module_name = (
                        entity.qualified_name.split(".")[0] if "." in entity.qualified_name else entity.qualified_name
                    )
                    if module_name not in imports_map:
                        imports_map[module_name] = []
                    imports_map[module_name].extend(entity.imports)

        self.manifest = ImplementationManifest(
            source_root=self.root,
            modules=modules,
            classes=classes,
            functions=functions,
            methods=methods,
            imports_map=imports_map,
        )

        _log.info("✅ 扫描完成:")
        _log.info("  模块：{len(modules)}")
        _log.info("  类：{len(classes)}")
        _log.info("  函数：{len(functions)}")
        _log.info("  方法：{len(methods)}")

        return self.manifest

    def _scan_file(self, file_path: Path) -> list[CodeEntity]:
        """扫描单个文件"""
        entities: list[CodeEntity] = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, OSError, ValueError):
            _log.info("  ⚠️  解析失败：{file_path} - {e}")
            return entities

        # 模块级信息
        module_name = file_path.stem
        qualified_prefix = self._get_qualified_prefix(file_path)

        # 模块实体
        module_entity = CodeEntity(
            id=f"mod_{module_name}",
            entity_type="module",
            name=module_name,
            qualified_name=qualified_prefix.rstrip("."),
            source_file=file_path,
            line_number=1,
            imports=self._extract_imports(tree),
        )
        entities.append(module_entity)

        # 遍历 AST
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_entity = self._scan_class(node, file_path, qualified_prefix)
                entities.append(class_entity)

                # 扫描类方法
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_entity = self._scan_method(item, file_path, f"{qualified_prefix}{node.name}")
                        entities.append(method_entity)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # 跳过类方法（已在上一步处理）
                parent_is_class = False
                # 检查这个函数是否是某个类的子节点
                for potential_parent in ast.walk(tree):
                    if isinstance(potential_parent, ast.ClassDef):
                        if node in potential_parent.body:
                            parent_is_class = True
                            break

                if not parent_is_class:
                    func_entity = self._scan_function(node, file_path, qualified_prefix)
                    entities.append(func_entity)

        return entities

    def _scan_class(self, node: ast.ClassDef, source_file: Path, qualified_prefix: str) -> CodeEntity:
        """扫描类定义"""
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(self._get_attribute_name(base))

        docstring = ast.get_docstring(node)

        return CodeEntity(
            id=f"class_{node.name}",
            entity_type="class",
            name=node.name,
            qualified_name=f"{qualified_prefix}{node.name}",
            source_file=source_file,
            line_number=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else None,
            base_classes=base_classes,
            decorators=[self._get_decorator_name(d) for d in node.decorator_list],
            docstring=docstring,
            is_abstract=any("ABC" in str(base) for base in base_classes),
            is_private=node.name.startswith("_"),
        )

    def _scan_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, source_file: Path, qualified_prefix: str
    ) -> CodeEntity:
        """扫描函数定义"""
        return CodeEntity(
            id=f"func_{node.name}",
            entity_type="function",
            name=node.name,
            qualified_name=f"{qualified_prefix}{node.name}",
            source_file=source_file,
            line_number=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else None,
            parameters=self._extract_parameters(node),
            return_type=self._extract_return_type(node),
            decorators=[self._get_decorator_name(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_private=node.name.startswith("_"),
        )

    def _scan_method(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, source_file: Path, qualified_prefix: str
    ) -> CodeEntity:
        """扫描方法定义"""
        return CodeEntity(
            id=f"method_{qualified_prefix}_{node.name}",
            entity_type="method",
            name=node.name,
            qualified_name=f"{qualified_prefix}.{node.name}",
            source_file=source_file,
            line_number=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else None,
            parameters=self._extract_parameters(node),
            return_type=self._extract_return_type(node),
            decorators=[self._get_decorator_name(d) for d in node.decorator_list],
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_private=node.name.startswith("_"),
            is_abstract=any(d.id == "abstractmethod" for d in node.decorator_list if isinstance(d, ast.Name)),
        )

    def _extract_imports(self, tree: ast.AST) -> list[str]:
        """提取导入语句"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports

    def _extract_parameters(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, Any]]:
        """提取参数"""
        parameters = []

        # 普通参数
        for arg in node.args.args:
            param: dict[str, Any] = {"name": arg.arg}
            if hasattr(arg, "annotation") and arg.annotation:
                try:
                    param["type"] = ast.unparse(arg.annotation)
                except (ValueError, AttributeError):
                    pass
            parameters.append(param)

        # *args
        if node.args.vararg:
            param = {"name": f"*{node.args.vararg.arg}", "variadic": True}
            if hasattr(node.args.vararg, "annotation") and node.args.vararg.annotation:
                try:
                    param["type"] = ast.unparse(node.args.vararg.annotation)
                except (ValueError, AttributeError):
                    pass
            parameters.append(param)

        # **kwargs
        if node.args.kwarg:
            param = {"name": f"**{node.args.kwarg.arg}", "variadic": True}
            if hasattr(node.args.kwarg, "annotation") and node.args.kwarg.annotation:
                try:
                    param["type"] = ast.unparse(node.args.kwarg.annotation)
                except (ValueError, AttributeError):
                    pass
            parameters.append(param)

        return parameters

    def _extract_return_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """提取返回类型"""
        if hasattr(node, "returns") and node.returns:
            try:
                return ast.unparse(node.returns)
            except (ValueError, AttributeError):
                pass
        return None

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """获取装饰器名称"""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return self._get_attribute_name(decorator)
        elif isinstance(decorator, ast.Call):
            return self._get_decorator_name(decorator.func)
        return str(decorator)

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """获取属性名称"""
        parts = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _get_qualified_prefix(self, file_path: Path) -> str:
        """获取限定名前缀"""
        try:
            rel_path = file_path.relative_to(self.root)
            parts = list(rel_path.parts[:-1])  # 去掉文件名

            # 移除常见的根目录
            if parts and parts[0] in ["organs", "nucleus", "src", "lib"]:
                parts = parts[1:]

            return ".".join(parts) + "." if parts else ""
        except ValueError:
            return ""

    def export_manifest(self, output_path: Path) -> None:
        """导出实现清单到 JSON"""
        if not self.manifest:
            raise ValueError("未扫描代码库，先调用 scan()")

        data = {
            "source_root": str(self.manifest.source_root),
            "summary": {
                "modules": len(self.manifest.modules),
                "classes": len(self.manifest.classes),
                "functions": len(self.manifest.functions),
                "methods": len(self.manifest.methods),
            },
            "modules": [
                {
                    "id": m.id,
                    "name": m.name,
                    "qualified_name": m.qualified_name,
                    "source_file": str(m.source_file),
                    "imports": m.imports,
                }
                for m in self.manifest.modules
            ],
            "classes": [
                {
                    "id": c.id,
                    "name": c.name,
                    "qualified_name": c.qualified_name,
                    "source_file": str(c.source_file),
                    "line_number": c.line_number,
                    "base_classes": c.base_classes,
                    "decorators": c.decorators,
                    "docstring": c.docstring[:100] if c.docstring else None,
                    "is_abstract": c.is_abstract,
                    "is_private": c.is_private,
                }
                for c in self.manifest.classes
            ],
            "functions_and_methods": [
                {
                    "id": f.id,
                    "name": f.name,
                    "qualified_name": f.qualified_name,
                    "entity_type": f.entity_type,
                    "source_file": str(f.source_file),
                    "line_number": f.line_number,
                    "parameters": f.parameters,
                    "return_type": f.return_type,
                    "is_async": f.is_async,
                    "is_abstract": f.is_abstract,
                }
                for f in self.manifest.functions + self.manifest.methods
            ],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        _log.info("✅ 实现清单已导出：{output_path}")
