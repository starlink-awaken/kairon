from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from eidos.organs.storage_dal import SQLiteRelationalProvider

"""
---
Type: Organ
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for organs/D-Memory/organs/knowledge_graph_engine.py'
Tags:
- auto-metadata
Authority: organs/D-Memory/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Knowledge Graph Engine ≡ Engine
# 内涵 ≝ {Knowledge, Graph, Engine}
# 外延 ≝ {e | e ∈ D-Memory ∧ implements(e, KnowledgeGraphEngine)}
# 功能 ⊢ {Knowledge_Graph, Graph_Engine, Engine_Init}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sage'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: D-Memory
Constraint: "[!!] KNOWLEDGE_GRAPH_ENGINE"
Summary: '知识图谱引擎 - 支持实体、关系和图查询'
Tags:
- knowledge
- graph
- nlp
- networkx
"""
_log = logging.getLogger(__name__)

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
type PropertiesMap = dict[str, JSONValue]


@dataclass
class Entity:
    """实体"""

    entity_id: str
    entity_type: str
    name: str
    properties: PropertiesMap
    embedding: np.ndarray | None = None
    domain: str = "unknown"
    created_at: float | None = None
    updated_at: float | None = None


@dataclass
class Relation:
    """关系"""

    relation_id: str
    source_entity: str
    target_entity: str
    relation_type: str
    properties: PropertiesMap
    weight: float = 1.0
    confidence: float = 1.0
    created_at: float | None = None
    updated_at: float | None = None


@dataclass
class Triple:
    """三元组"""

    subject: str
    predicate: str
    object: str
    confidence: float = 1.0


class KnowledgeGraphEngine:
    """知识图谱引擎"""

    def __init__(self, metadata_path: str) -> None:
        self.status = "active"
        self.metadata_path = metadata_path

        # 实体索引
        self.entities: dict[str, Entity] = {}

        # 关系索引
        self.relations: dict[str, Relation] = {}

        # 类型索引
        self.entities_by_type: dict[str, set[str]] = defaultdict(set)

        # 关系类型索引
        self.relations_by_type: dict[str, set[str]] = defaultdict(set)

        # 域索引
        self.entities_by_domain: dict[str, set[str]] = defaultdict(set)

        # 统计
        self.total_entities = 0
        self.total_relations = 0

        # 初始化数据库
        db_path = str(Path(self.metadata_path).parent.parent / "data" / (Path(self.metadata_path).stem + ".db"))
        self._db = SQLiteRelationalProvider(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        self._db.execute("PRAGMA journal_mode=WAL")

        # 实体表
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                properties TEXT NOT NULL,
                domain TEXT NOT NULL,
                embedding BLOB,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """
        )

        # 关系表
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS kg_relations (
                relation_id TEXT PRIMARY KEY,
                source_entity TEXT NOT NULL,
                target_entity TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                properties TEXT NOT NULL,
                weight REAL NOT NULL,
                confidence REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (source_entity) REFERENCES kg_entities(entity_id),
                FOREIGN KEY (target_entity) REFERENCES kg_entities(entity_id)
            )
        """
        )

        # 创建索引
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON kg_entities(entity_type)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_entities_domain ON kg_entities(domain)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON kg_relations(source_entity)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON kg_relations(target_entity)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_relations_type ON kg_relations(relation_type)")

    def add_entity(
        self,
        entity_id: str,
        entity_type: str,
        name: str,
        properties: PropertiesMap,
        embedding: np.ndarray | None = None,
        domain: str = "unknown",
    ) -> str:
        """
        添加实体

        Args:
            entity_id: 实体ID
            entity_type: 实体类型
            name: 实体名称
            properties: 属性字典
            embedding: 向量嵌入
            domain: 所属域

        Returns:
            实体ID
        """
        entity = Entity(
            entity_id=entity_id,
            entity_type=entity_type,
            name=name,
            properties=properties,
            embedding=embedding,
            domain=domain,
            created_at=time.time(),
            updated_at=time.time(),
        )

        self.entities[entity_id] = entity
        self.entities_by_type[entity_type].add(entity_id)
        self.entities_by_domain[domain].add(entity_id)
        self.total_entities += 1

        # 保存到数据库
        self._save_entity(entity)

        self._log(f"Entity added: {entity_id} (type: {entity_type}, domain: {domain})")

        return entity_id

    def add_relation(
        self,
        relation_id: str,
        source_entity: str,
        target_entity: str,
        relation_type: str,
        properties: PropertiesMap,
        weight: float = 1.0,
        confidence: float = 1.0,
    ) -> str:
        """
        添加关系

        Args:
            relation_id: 关系ID
            source_entity: 源实体ID
            target_entity: 目标实体ID
            relation_type: 关系类型
            properties: 属性字典
            weight: 权重
            confidence: 置信度

        Returns:
            关系ID
        """
        relation = Relation(
            relation_id=relation_id,
            source_entity=source_entity,
            target_entity=target_entity,
            relation_type=relation_type,
            properties=properties,
            weight=weight,
            confidence=confidence,
            created_at=time.time(),
            updated_at=time.time(),
        )

        self.relations[relation_id] = relation
        self.relations_by_type[relation_type].add(relation_id)
        self.total_relations += 1

        # 保存到数据库
        self._save_relation(relation)

        self._log(f"Relation added: {relation_id} (type: {relation_type}, confidence: {confidence})")

        return relation_id

    def get_entity(self, entity_id: str) -> Entity | None:
        """
        获取实体

        Args:
            entity_id: 实体ID

        Returns:
            实体对象
        """
        return self.entities.get(entity_id)

    def get_relation(self, relation_id: str) -> Relation | None:
        """
        获取关系

        Args:
            relation_id: 关系ID

        Returns:
            关系对象
        """
        return self.relations.get(relation_id)

    def query_entities(
        self,
        entity_type: str | None = None,
        domain: str | None = None,
        properties: PropertiesMap | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """
        查询实体

        Args:
            entity_type: 实体类型
            domain: 域
            properties: 属性过滤
            limit: 最大返回数量

        Returns:
            实体列表
        """
        results = []

        for entity in self.entities.values():
            # 类型过滤
            if entity_type and entity.entity_type != entity_type:
                continue

            # 域过滤
            if domain and entity.domain != domain:
                continue

            # 属性过滤
            if properties:
                match = True
                for key, value in properties.items():
                    if key not in entity.properties or entity.properties[key] != value:
                        match = False
                        break
                if not match:
                    continue

            results.append(entity)

            if len(results) >= limit:
                break

        return results

    def query_relations(
        self,
        source_entity: str | None = None,
        target_entity: str | None = None,
        relation_type: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> list[Relation]:
        """
        查询关系

        Args:
            source_entity: 源实体ID
            target_entity: 目标实体ID
            relation_type: 关系类型
            min_confidence: 最小置信度
            limit: 最大返回数量

        Returns:
            关系列表
        """
        results = []

        for relation in self.relations.values():
            # 源实体过滤
            if source_entity and relation.source_entity != source_entity:
                continue

            # 目标实体过滤
            if target_entity and relation.target_entity != target_entity:
                continue

            # 关系类型过滤
            if relation_type and relation.relation_type != relation_type:
                continue

            # 置信度过滤
            if relation.confidence < min_confidence:
                continue

            results.append(relation)

            if len(results) >= limit:
                break

        return results

    def find_path(
        self,
        source_entity: str,
        target_entity: str,
        max_depth: int = 3,
        relation_types: list[str] | None = None,
    ) -> list[list[str]]:
        """
        查找两个实体之间的路径（BFS）

        Args:
            source_entity: 源实体ID
            target_entity: 目标实体ID
            max_depth: 最大深度
            relation_types: 关系类型过滤

        Returns:
            路径列表
        """
        from collections import deque

        if source_entity not in self.entities or target_entity not in self.entities:
            return []

        # 构建邻接表
        adjacency = defaultdict(list)
        for relation in self.relations.values():
            # 关系类型过滤
            if relation_types and relation.relation_type not in relation_types:
                continue

            # 双向边
            adjacency[relation.source_entity].append(relation.target_entity)
            adjacency[relation.target_entity].append(relation.source_entity)

        # BFS 搜索
        queue: deque[tuple[Any, list[Any]]] = deque([(source_entity, [])])
        visited = {source_entity}
        paths = []

        while queue:
            current, path = queue.popleft()

            if current == target_entity:
                paths.append(path + [current])
                continue

            if len(path) >= max_depth:
                continue

            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [current]
                    queue.append((neighbor, new_path))

        return paths

    def get_statistics(self) -> dict[str, int]:
        """获取统计信息"""
        return {
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "entity_types": len(self.entities_by_type),
            "relation_types": len(self.relations_by_type),
            "domains": len(self.entities_by_domain),
        }

    def _save_entity(self, entity: Entity) -> None:
        """保存实体到数据库"""
        # 序列化嵌入
        embedding_blob = None
        if entity.embedding is not None:
            embedding_blob = entity.embedding.tobytes()

        self._db.execute_write(
            """
            INSERT OR REPLACE INTO kg_entities
            (entity_id, entity_type, name, properties, domain, embedding, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM kg_entities WHERE entity_id = ?), ?), ?)
        """,
            (
                entity.entity_id,
                entity.entity_type,
                entity.name,
                json.dumps(entity.properties),
                entity.domain,
                embedding_blob,
                entity.entity_id,
                entity.created_at,
                entity.updated_at,
            ),
        )

    def _save_relation(self, relation: Relation) -> None:
        """保存关系到数据库"""
        self._db.execute_write(
            """
            INSERT OR REPLACE INTO kg_relations
            (relation_id, source_entity, target_entity, relation_type, properties, weight, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM kg_relations WHERE relation_id = ?), ?), ?)
        """,
            (
                relation.relation_id,
                relation.source_entity,
                relation.target_entity,
                relation.relation_type,
                json.dumps(relation.properties),
                relation.weight,
                relation.confidence,
                relation.relation_id,
                relation.created_at,
                relation.updated_at,
            ),
        )

    def _log(self, message: str) -> None:
        """记录日志"""
        _log.info("[KnowledgeGraphEngine] %s", message)

    def ping(self) -> bool:
        """健康检查"""
        return True

    def validate_internal_state(self) -> bool:
        """验证内部状态：检查数据库连接、表结构和基本数据完整性。

        Returns:
            True  — 状态正常
            False — 检测到问题
        """
        try:
            # 2. 必要的表是否存在
            required_tables = {"kg_entities", "kg_relations"}
            rows = self._db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row["name"] for row in rows}
            missing = required_tables - existing_tables
            if missing:
                _log.warning("[KnowledgeGraphEngine] 缺少必要的表: %s", missing)
                return False

            # 3. 节点/边计数基本一致性校验
            entity_row = self._db.fetch_one("SELECT COUNT(*) FROM kg_entities")
            db_entity_count = entity_row["COUNT(*)"]
            relation_row = self._db.fetch_one("SELECT COUNT(*) FROM kg_relations")
            db_relation_count = relation_row["COUNT(*)"]

            # 内存索引与数据库记录数应相符（允许短暂不一致）
            mem_entity_count = len(self.entities)
            mem_relation_count = len(self.relations)
            if mem_entity_count > db_entity_count:
                _log.warning(
                    "[KnowledgeGraphEngine] 内存实体数 (%d) > 数据库记录数 (%d)",
                    mem_entity_count,
                    db_entity_count,
                )
                return False
            if mem_relation_count > db_relation_count:
                _log.warning(
                    "[KnowledgeGraphEngine] 内存关系数 (%d) > 数据库记录数 (%d)",
                    mem_relation_count,
                    db_relation_count,
                )
                return False

            _log.info(
                "[KnowledgeGraphEngine] 内部状态正常 — 实体: %d, 关系: %d",
                db_entity_count,
                db_relation_count,
            )
            return True

        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            _log.error("[KnowledgeGraphEngine] validate_internal_state 失败: %s", e)
            return False
