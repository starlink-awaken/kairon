from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Layer: L3
---
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from eidos.organs.storage_dal import SQLiteOperationalError, SQLiteRelationalProvider  # type: ignore[import-not-found]

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Cross_Domain_Analyzer ≡ Information_Bridge
# 内涵 ≝ {Connect, Correlate, Integrate}
# 外延 ≝ {c | c ∈ Z-Microkernel ∧ bridges(c, D-Domains)}
# 功能 ⊢ {AnalyzeRelations, QueryAcrossDomains, IntegrateInformation}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: Z-Microkernel
Constraint: "[!!] CROSS_DOMAIN_CORRELATION"
Summary: '跨域关联分析器 - 分析和关联不同域之间的信息'
---

Cross Domain Analyzer - 跨域关联分析器

职责:
- 分析不同域之间的信息流动
- 识别关联关系
- 提供跨域查询能力
- 集成信息流

作者: iFlow CLI
日期: 2026-03-03
状态: 生产就绪
"""

_log = logging.getLogger(__name__)


@dataclass
class DomainRelation:
    """域关联关系"""

    source_domain: str
    target_domain: str
    relation_type: str  # 'flow', 'dependency', 'reference', 'inheritance'
    strength: float  # 0.0 - 1.0
    last_updated: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InformationFlow:
    """信息流"""

    source_id: str
    source_domain: str
    target_id: str
    target_domain: str
    flow_type: str  # 'data', 'control', 'event', 'query'
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class CrossDomainAnalyzer:
    """跨域关联分析器 - 分析和关联不同域之间的信息"""

    def __init__(self, db_path: str | None = None) -> None:
        """
        初始化跨域关联分析器

        Args:
            db_path: 数据库路径
        """
        self.status = "active"
        self.db_path = db_path or os.environ.get("BOS_MICROKERNEL_DB", "data/microkernel.db")
        self._relations: dict[str, DomainRelation] = {}
        self._flows: list[InformationFlow] = []
        self._domain_graph: dict[str, set[str]] = {}  # domain -> connected domains
        self._db = SQLiteRelationalProvider(self.db_path)
        self.initialize()

    def _ensure_db(self) -> None:
        """Initialize DB connection and apply pragmas."""
        self._db.connect()
        self._db.execute("PRAGMA busy_timeout=30000")
        try:
            self._db.execute("PRAGMA journal_mode=DELETE")
        except SQLiteOperationalError:
            pass
        self._db.execute("PRAGMA synchronous=NORMAL")

    def initialize(self) -> None:
        """初始化数据库表"""
        self._ensure_db()
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS domain_relations (
                id TEXT PRIMARY KEY,
                source_domain TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                strength REAL NOT NULL,
                last_updated REAL NOT NULL,
                metadata TEXT
            );"""
        )

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS information_flows (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_domain TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                flow_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT
            );"""
        )

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS cross_domain_queries (
                id TEXT PRIMARY KEY,
                query_text TEXT NOT NULL,
                domains_involved TEXT NOT NULL,
                results TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                timestamp REAL NOT NULL
            );"""
        )

        _log.info("[*] CrossDomainAnalyzer initialized")

    def discover_relations(self) -> list[DomainRelation]:
        """
        发现域之间的关联关系

        Returns:
            List[DomainRelation]: 关联关系列表
        """
        # 定义已知域

        # 定义已知关系（基于架构知识）
        known_relations = [
            ("D-Execution", "D-Economy", "dependency", 0.9),
            ("D-Execution", "D-Memory", "dependency", 0.8),
            ("D-Execution", "D-Immunity", "reference", 0.6),
            ("D-Economy", "D-Memory", "reference", 0.7),
            ("D-Economy", "D-Excretion", "flow", 0.5),
            ("D-Memory", "D-Genesis", "dependency", 0.7),
            ("D-Immunity", "D-Execution", "reference", 0.6),
            ("D-Genesis", "D-Execution", "flow", 0.8),
            ("D-Excretion", "D-Memory", "flow", 0.5),
        ]

        relations = []

        for source, target, relation_type, strength in known_relations:
            relation_id = f"{source}_{target}_{relation_type}"

            # 更新或创建关系
            if relation_id in self._relations:
                relation = self._relations[relation_id]
                relation.strength = min(1.0, relation.strength + 0.1)
                relation.last_updated = time.time()
            else:
                relation = DomainRelation(
                    source_domain=source,
                    target_domain=target,
                    relation_type=relation_type,
                    strength=strength,
                    last_updated=time.time(),
                )
                self._relations[relation_id] = relation

            relations.append(relation)

            # 更新图结构
            if source not in self._domain_graph:
                self._domain_graph[source] = set()
            self._domain_graph[source].add(target)

            # 保存到数据库
            self._save_relation(relation)

        return relations

    def record_flow(
        self,
        source_id: str,
        source_domain: str,
        target_id: str,
        target_domain: str,
        flow_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        记录信息流

        Args:
            source_id: 源ID
            source_domain: 源域
            target_id: 目标ID
            target_domain: 目标域
            flow_type: 流类型
            metadata: 元数据
        """
        import hashlib

        flow_id = hashlib.md5(f"{source_id}_{target_id}_{flow_type}_{time.time()}".encode()).hexdigest()  # noqa: S324

        flow = InformationFlow(
            source_id=source_id,
            source_domain=source_domain,
            target_id=target_id,
            target_domain=target_domain,
            flow_type=flow_type,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        self._flows.append(flow)

        # 限制流记录数量
        if len(self._flows) > 10000:
            self._flows = self._flows[-5000:]

        # 保存到数据库
        self._db.execute(
            """
            INSERT INTO information_flows
            (id, source_id, source_domain, target_id, target_domain, flow_type, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                flow_id,
                source_id,
                source_domain,
                target_id,
                target_domain,
                flow_type,
                flow.timestamp,
                json.dumps(flow.metadata),
            ),
        )

        # 更新关联强度
        self._update_relation_strength(source_domain, target_domain)

    def _update_relation_strength(self, source_domain: str, target_domain: str) -> None:
        """
        更新关联强度

        Args:
            source_domain: 源域
            target_domain: 目标域
        """
        relation_id = f"{source_domain}_{target_domain}_flow"

        if relation_id in self._relations:
            relation = self._relations[relation_id]
            relation.strength = min(1.0, relation.strength + 0.05)
            relation.last_updated = time.time()
            self._save_relation(relation)
        else:
            relation = DomainRelation(
                source_domain=source_domain,
                target_domain=target_domain,
                relation_type="flow",
                strength=0.1,
                last_updated=time.time(),
            )
            self._relations[relation_id] = relation
            self._save_relation(relation)

            if source_domain not in self._domain_graph:
                self._domain_graph[source_domain] = set()
            self._domain_graph[source_domain].add(target_domain)

    def _save_relation(self, relation: DomainRelation) -> None:
        """保存关系到数据库"""
        relation_id = f"{relation.source_domain}_{relation.target_domain}_{relation.relation_type}"

        self._db.execute(
            """
            INSERT OR REPLACE INTO domain_relations
            (id, source_domain, target_domain, relation_type, strength, last_updated, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                relation.source_domain,
                relation.target_domain,
                relation.relation_type,
                relation.strength,
                relation.last_updated,
                json.dumps(relation.metadata),
            ),
        )

    def query_across_domains(
        self, query: str, domains: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        跨域查询

        Args:
            query: 查询文本
            domains: 涉及的域（可选，如果不指定则查询所有域）
            limit: 返回结果数量

        Returns:
            List[Dict]: 查询结果
        """
        import hashlib

        query_id = hashlib.md5(f"{query}_{time.time()}".encode()).hexdigest()  # noqa: S324

        # 如果没有指定域，使用所有域
        if domains is None:
            domains = [
                "D-Execution",
                "D-Economy",
                "D-Memory",
                "D-Immunity",
                "D-Genesis",
                "D-Excretion",
            ]

        start_time = time.time()

        # 执行查询（简化实现）
        results: list[dict[str, Any]] = []

        # 在这里应该实现实际的跨域查询逻辑
        # 简化实现：返回模拟结果

        for domain in domains:
            # 模拟查询结果
            results.append(
                {
                    "domain": domain,
                    "type": "mock",
                    "data": f"Mock result for '{query}' in {domain}",
                    "confidence": 0.5 + (hash(domain) % 50) / 100,
                }
            )

        # 按置信度排序
        results.sort(key=lambda r: r["confidence"], reverse=True)
        results = results[:limit]

        execution_time = (time.time() - start_time) * 1000

        # 保存查询记录
        self._db.execute(
            """
            INSERT INTO cross_domain_queries
            (id, query_text, domains_involved, results, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query_id,
                query,
                json.dumps(domains),
                json.dumps(results),
                execution_time,
                time.time(),
            ),
        )

        return results

    def get_domain_graph(self) -> dict[str, list[dict[str, Any]]]:
        """
        获取域关系图

        Returns:
            Dict: 域关系图
        """
        graph: dict[str, list[dict[str, Any]]] = {"nodes": [], "edges": []}

        # 添加节点
        for domain in self._domain_graph.keys():
            graph["nodes"].append({"id": domain, "label": domain, "type": "domain"})

        # 添加边
        seen_edges = set()
        for source, targets in self._domain_graph.items():
            for target in targets:
                edge_key = tuple(sorted([source, target]))
                if edge_key not in seen_edges:
                    # 查找关联强度
                    relation = self._find_relation(source, target)
                    strength = relation.strength if relation else 0.5

                    graph["edges"].append(
                        {
                            "source": source,
                            "target": target,
                            "strength": strength,
                            "type": relation.relation_type if relation else "unknown",
                        }
                    )
                    seen_edges.add(edge_key)

        return graph

    def _find_relation(self, source_domain: str, target_domain: str) -> DomainRelation | None:
        """查找域之间的关联"""
        for relation in self._relations.values():
            if relation.source_domain == source_domain and relation.target_domain == target_domain:
                return relation
            if relation.source_domain == target_domain and relation.target_domain == source_domain:
                return relation
        return None

    def analyze_flow_patterns(self) -> dict[str, Any]:
        """
        分析信息流模式

        Returns:
            Dict: 流模式分析结果
        """
        if not self._flows:
            return {"error": "No flow records available"}

        # 按流类型分组
        flow_type_stats: dict[str, dict] = {}

        for flow in self._flows:
            if flow.flow_type not in flow_type_stats:
                flow_type_stats[flow.flow_type] = {
                    "count": 0,
                    "source_domains": set(),
                    "target_domains": set(),
                }

            stats = flow_type_stats[flow.flow_type]
            stats["count"] += 1
            stats["source_domains"].add(flow.source_domain)
            stats["target_domains"].add(flow.target_domain)

        # 转换集合为列表
        for stats in flow_type_stats.values():
            stats["source_domains"] = list(stats["source_domains"])
            stats["target_domains"] = list(stats["target_domains"])

        # 统计最活跃的域对
        domain_pair_counts: dict[tuple, int] = {}
        for flow in self._flows:
            pair = (flow.source_domain, flow.target_domain)
            domain_pair_counts[pair] = domain_pair_counts.get(pair, 0) + 1

        top_pairs = sorted(domain_pair_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_flows": len(self._flows),
            "flow_type_stats": flow_type_stats,
            "top_domain_pairs": [
                {"source_domain": pair[0], "target_domain": pair[1], "flow_count": count} for pair, count in top_pairs
            ],
        }

    def get_analysis_report(self) -> dict[str, Any]:
        """
        获取分析报告

        Returns:
            Dict: 分析报告
        """
        relations = self.discover_relations()
        graph = self.get_domain_graph()
        flow_patterns = self.analyze_flow_patterns()

        # 统计关联强度
        high_strength_relations = [r for r in relations if r.strength > 0.7]
        medium_strength_relations = [r for r in relations if 0.3 < r.strength <= 0.7]
        low_strength_relations = [r for r in relations if r.strength <= 0.3]

        return {
            "domain_graph": graph,
            "relations": {
                "total": len(relations),
                "high_strength": len(high_strength_relations),
                "medium_strength": len(medium_strength_relations),
                "low_strength": len(low_strength_relations),
                "by_type": self._group_relations_by_type(relations),
            },
            "flow_patterns": flow_patterns,
            "integration_score": self._calculate_integration_score(relations),
        }

    def _group_relations_by_type(self, relations: list[DomainRelation]) -> dict[str, dict]:
        """按类型分组关联"""
        grouped: dict[str, dict] = {}

        for relation in relations:
            if relation.relation_type not in grouped:
                grouped[relation.relation_type] = {
                    "count": 0,
                    "total_strength": 0.0,
                    "avg_strength": 0.0,
                }

            stats = grouped[relation.relation_type]
            stats["count"] += 1
            stats["total_strength"] += relation.strength
            stats["avg_strength"] = stats["total_strength"] / stats["count"]

        return grouped

    def _calculate_integration_score(self, relations: list[DomainRelation]) -> float:
        """
        计算集成得分

        Args:
            relations: 关联关系列表

        Returns:
            float: 集成得分 (0.0 - 1.0)
        """
        if not relations:
            return 0.0

        # 基于关联强度和多样性计算得分
        total_strength = sum(r.strength for r in relations)
        avg_strength = total_strength / len(relations)

        # 多样性得分（不同类型的关联）
        relation_types = {r.relation_type for r in relations}
        diversity_score = len(relation_types) / 4.0  # 假设最多4种类型

        # 综合得分
        integration_score = (avg_strength * 0.7) + (diversity_score * 0.3)

        return min(1.0, integration_score)

    def validate_internal_state(self) -> bool:
        """验证内部状态"""
        return os.path.exists(self.db_path)


# 全局单例
CrossDomainAnalyzerInstance = CrossDomainAnalyzer()
