from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

_log = logging.getLogger(__name__)


class RequirementStatus(Enum):
    """需求状态"""

    DRAFT = "draft"  # 草稿
    REVIEW = "review"  # 评审中
    APPROVED = "approved"  # 已批准
    IMPLEMENTING = "implementing"  # 实现中
    IMPLEMENTED = "implemented"  # 已实现
    ARCHIVED = "archived"  # 已归档


class RequirementType(Enum):
    """需求类型"""

    FUNCTIONAL = "functional"  # 功能需求
    NON_FUNCTIONAL = "non_functional"  # 非功能需求
    TECHNICAL = "technical"  # 技术需求
    BUSINESS = "business"  # 业务需求


@dataclass
class Requirement:
    """需求"""

    # 基本信息
    id: str  # 唯一标识符 (e.g., "REQ-001")
    title: str  # 需求标题
    type: RequirementType  # 需求类型
    status: RequirementStatus  # 状态

    # 内容
    description: str  # 详细描述
    acceptance_criteria: list[str] = field(default_factory=list)  # 验收标准

    # 元数据
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    author: str | None = None
    priority: str = "P2"  # P0/P1/P2

    # 追踪
    parent_id: str | None = None  # 父需求 ID
    child_ids: list[str] = field(default_factory=list)  # 子需求 ID
    related_code_entities: list[str] = field(default_factory=list)  # 关联的代码实体
    related_tests: list[str] = field(default_factory=list)  # 关联的测试

    # 来源
    source_file: Path | None = None
    source_line: int | None = None


@dataclass
class TraceabilityMatrix:
    """需求追踪矩阵"""

    requirements: list[Requirement]
    code_links: dict[str, list[str]]  # req_id -> [code_entity]
    test_links: dict[str, list[str]]  # req_id -> [test_id]
    coverage: float  # 需求覆盖率


class RequirementManager:
    """需求管理器"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.requirements: dict[str, Requirement] = {}
        self.requirements_dir = root / "data" / "requirements"
        self.requirements_dir.mkdir(parents=True, exist_ok=True)
        self._metrics: dict = {
            "requirements_created": 0,
            "requirements_updated": 0,
            "errors": 0,
        }

    def health_check(self) -> dict:
        """Return health metrics for RequirementManager.

        Returns:
            dict with status, version, requirement_count, and storage path.
        """
        return {
            "status": "healthy",
            "version": "1.0.0",
            "organ": "RequirementManager",
            "requirement_count": len(self.requirements),
            "requirements_dir": str(self.requirements_dir),
            "requirements_dir_exists": self.requirements_dir.exists(),
            "metrics": self._metrics,
        }

    def describe(self) -> dict:
        """Return capability descriptor for RequirementManager.

        Returns:
            dict with name, version, capabilities, and bos_uri.
        """
        return {
            "name": "RequirementManager",
            "version": "1.0.0",
            "capabilities": [
                "req.create",
                "req.update",
                "req.link_to_code",
                "req.impact_analysis",
                "req.export_json",
            ],
            "bos_uri": "bos://d-logos/req-manager",
        }

    def heartbeat(self) -> dict:
        """Return liveness heartbeat for RequirementManager.

        Returns:
            dict with status, ts, and requirement_count.
        """
        return {
            "status": "alive",
            "ts": __import__("time").time(),
            "requirement_count": len(self.requirements),
            "metrics": self._metrics,
        }

    def create_requirement(
        self,
        title: str,
        req_type: RequirementType,
        description: str,
        author: str | None = None,
        priority: str = "P2",
    ) -> Requirement:
        """创建新需求"""
        # 生成需求 ID
        req_id = self._generate_req_id()

        req = Requirement(
            id=req_id,
            title=title,
            type=req_type,
            status=RequirementStatus.DRAFT,
            description=description,
            author=author,
            priority=priority,
        )

        self.requirements[req_id] = req
        _log.info("✅ 需求已创建: {req_id} - {title}")  # noqa: F821
        return req

    def update_requirement(self, req_id: str, **kwargs: object) -> Requirement | None:
        """更新需求"""
        if req_id not in self.requirements:
            _log.info("❌ 需求不存在: {req_id}")  # noqa: F821
            return None

        req = self.requirements[req_id]

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(req, key):
                setattr(req, key, value)

        req.updated_at = datetime.now().timestamp()
        _log.info("✅ 需求已更新: {req_id}")  # noqa: F821
        return req

    def link_to_code(self, req_id: str, code_entity: str) -> bool:
        """关联需求到代码实体"""
        if req_id not in self.requirements:
            _log.info("❌ 需求不存在: {req_id}")  # noqa: F821
            return False

        req = self.requirements[req_id]
        if code_entity not in req.related_code_entities:
            req.related_code_entities.append(code_entity)
            req.updated_at = datetime.now().timestamp()

        _log.info("✅ 需求 {req_id} 关联到代码: {code_entity}")  # noqa: F821
        return True

    def link_to_test(self, req_id: str, test_id: str) -> bool:
        """关联需求到测试"""
        if req_id not in self.requirements:
            _log.info("❌ 需求不存在: {req_id}")  # noqa: F821
            return False

        req = self.requirements[req_id]
        if test_id not in req.related_tests:
            req.related_tests.append(test_id)
            req.updated_at = datetime.now().timestamp()

        _log.info("✅ 需求 {req_id} 关联到测试: {test_id}")  # noqa: F821
        return True

    def change_status(self, req_id: str, new_status: RequirementStatus) -> Requirement | None:
        """变更需求状态"""
        if req_id not in self.requirements:
            _log.info("❌ 需求不存在: {req_id}")  # noqa: F821
            return None

        req = self.requirements[req_id]
        req.status = new_status
        req.updated_at = datetime.now().timestamp()

        _log.info("✅ 需求 {req_id} 状态变更: {old_status.value} → {new_status.value}")  # noqa: F821
        return req

    def analyze_impact(self, req_id: str) -> dict:
        """分析需求变更的影响"""
        if req_id not in self.requirements:
            return {}

        req = self.requirements[req_id]

        impact = {
            "requirement": req_id,
            "child_requirements": req.child_ids,
            "related_code": req.related_code_entities,
            "related_tests": req.related_tests,
            "total_impact": (len(req.child_ids) + len(req.related_code_entities) + len(req.related_tests)),
        }

        return impact

    def get_traceability_matrix(self) -> TraceabilityMatrix:
        """获取需求追踪矩阵"""
        code_links: dict[str, list[str]] = {}
        test_links: dict[str, list[str]] = {}

        for req_id, req in self.requirements.items():
            if req.related_code_entities:
                code_links[req_id] = req.related_code_entities
            if req.related_tests:
                test_links[req_id] = req.related_tests

        # 计算覆盖率
        total_reqs = len(self.requirements)
        implemented_reqs = sum(1 for req in self.requirements.values() if req.status == RequirementStatus.IMPLEMENTED)
        coverage = implemented_reqs / total_reqs * 100 if total_reqs > 0 else 0.0

        return TraceabilityMatrix(
            requirements=list(self.requirements.values()),
            code_links=code_links,
            test_links=test_links,
            coverage=coverage,
        )

    def extract_from_markdown(self, md_file: Path) -> list[Requirement]:
        """从 Markdown 文档提取需求"""
        if not md_file.exists():
            return []

        content = md_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        reqs = []

        # 简单的需求提取模式
        # 匹配: ## REQ-001: 需求标题
        pattern = r"^##+\s+(REQ-\d+):\s+(.+)$"

        for i, line in enumerate(lines):
            match = re.match(pattern, line.strip())
            if match:
                req_id = match.group(1)
                title = match.group(2)

                # 提取描述（直到下一个需求或文档结束）
                description_lines = []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if re.match(r"^##+\s+REQ-\d+:", next_line):
                        break
                    if next_line:
                        description_lines.append(next_line)

                req = Requirement(
                    id=req_id,
                    title=title,
                    type=RequirementType.FUNCTIONAL,
                    status=RequirementStatus.DRAFT,
                    description="\n".join(description_lines),
                    source_file=md_file,
                    source_line=i + 1,
                )

                self.requirements[req_id] = req
                reqs.append(req)

        _log.info("✅ 从 {md_file.name} 提取了 {len(reqs)} 个需求")  # noqa: F821
        return reqs

    def export_json(self, output_path: Path) -> None:
        """导出需求到 JSON"""
        data = {
            "requirements": [
                {
                    "id": req.id,
                    "title": req.title,
                    "type": req.type.value,
                    "status": req.status.value,
                    "description": req.description,
                    "acceptance_criteria": req.acceptance_criteria,
                    "created_at": req.created_at,
                    "updated_at": req.updated_at,
                    "author": req.author,
                    "priority": req.priority,
                    "related_code_entities": req.related_code_entities,
                    "related_tests": req.related_tests,
                }
                for req in self.requirements.values()
            ],
            "summary": {
                "total": len(self.requirements),
                "by_status": {
                    status.value: sum(1 for req in self.requirements.values() if req.status == status)
                    for status in RequirementStatus
                },
                "by_type": {
                    type.value: sum(1 for req in self.requirements.values() if req.type == type)
                    for type in RequirementType
                },
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        _log.info("✅ 需求已导出: {output_path}")  # noqa: F821

    def _generate_req_id(self) -> str:
        """生成需求 ID"""
        existing_ids = [
            int(req_id.split("-")[1])
            for req_id in self.requirements.keys()
            if req_id.startswith("REQ-") and req_id.split("-")[1].isdigit()
        ]

        next_num = max(existing_ids) + 1 if existing_ids else 1
        return f"REQ-{next_num:03d}"

    def load_requirements(self) -> None:
        """加载需求"""
        req_file = self.requirements_dir / "requirements.json"
        if req_file.exists():
            with open(req_file, encoding="utf-8") as f:
                data = json.load(f)
                req_list = data.get("requirements", [])
                for req_data in req_list:
                    req = Requirement(
                        id=req_data["id"],
                        title=req_data["title"],
                        type=RequirementType(req_data["type"]),
                        status=RequirementStatus(req_data["status"]),
                        description=req_data["description"],
                        acceptance_criteria=req_data.get("acceptance_criteria", []),
                        created_at=req_data.get("created_at", datetime.now().timestamp()),
                        updated_at=req_data.get("updated_at", datetime.now().timestamp()),
                        author=req_data.get("author"),
                        priority=req_data.get("priority", "P2"),
                        parent_id=req_data.get("parent_id"),
                        child_ids=req_data.get("child_ids", []),
                        related_code_entities=req_data.get("related_code_entities", []),
                        related_tests=req_data.get("related_tests", []),
                    )
                    self.requirements[req.id] = req
                _log.info("✅ 已加载 {len(req_list)} 个需求")  # noqa: F821

    def save_requirements(self) -> None:
        """保存需求"""
        self.export_json(self.requirements_dir / "requirements.json")
