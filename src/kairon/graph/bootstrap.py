"""KEMS-v2 seed corpus bootstrap.

Builds a deterministic synthetic corpus of:
  - 2000 政策 (Policy) entries
  - 1500 规程 (Regulation) entries
  - 1000 架构决策 (ADR) entries
  -  500 历史批复 (Approval) entries
  Total: 5000 entities.

Edges are generated to reach ≥ 20000 total:
  - Each policy cites 3-5 regulations
  - Each regulation implements 2-4 policies
  - Each ADR references 5-10 entities
  - Each approval cites 1-3 policies

All content is deterministic (seeded by entity id) so eval runs are reproducible.
Real policy/regulation/ADR/approval text from public sources would replace this in
production; this is the offline-OK seed for the v1 delivery.
"""

from __future__ import annotations

import hashlib
import random
from typing import Callable

from kairon.graph.kems_v2 import (
    Edge,
    Entity,
    EntityType,
    KnowledgeGraph,
    RelationType,
)

# 政策主题 — 卫生健康 + 通用政务
POLICY_THEMES = [
    "卫生健康数字化转型", "健康中国战略", "公立医院高质量发展", "基层卫生服务能力",
    "公共卫生应急体系", "国家基本药物制度", "医疗保障支付方式改革", "分级诊疗制度",
    "互联网+医疗健康", "健康医疗大数据应用", "药品集中采购", "医保异地就医结算",
    "电子健康档案共享", "人口健康信息服务", "老年人健康保障", "妇幼健康促进",
    "职业病防治", "健康扶贫", "医疗联合体建设", "智慧医院建设",
    "中医药传承创新", "重大疾病防控", "健康产业监管", "健康保险制度完善",
]

REGULATION_THEMES = [
    "医疗机构管理条例", "医师执业注册办法", "医疗事故处理条例", "药品管理法实施条例",
    "传染病防治法实施办法", "公共场所卫生管理条例", "学校卫生工作条例",
    "医疗机构药品集中招标采购工作规范", "处方管理办法", "病历书写基本规范",
    "医疗废物管理条例", "护士条例", "母婴保健法实施办法", "职业病诊断与鉴定管理办法",
    "医疗机构制剂注册管理办法", "医疗广告管理办法", "互联网医疗管理办法",
    "医疗知情同意规范", "医疗质量管理办法", "卫生行政许可办法",
    "医疗设备管理办法", "生物安全法实施办法", "国家基本公共卫生服务规范",
    "医疗机构校验管理办法",
]

ADR_THEMES = [
    "kairon 知识图谱 schema 选型", "BM25 vs 向量检索 trade-off", "JSONL 持久化 vs SQLite",
    "CJK 分词策略", "Spine 集成: 实体引用 vs URL 引用", "BFS vs 双向遍历",
    "policy 命名空间: dot vs dash", "approval 跨域桥接", "ADR 与 policy 引用方向",
    "图遍历深度限制", "图谱 schema 演进", "entity id 生成策略", "metadata 字段 schema",
    "检索打分融合公式", "Top-K 重排序", "向量索引: pgvector vs faiss",
    "图 + 向量混合召回", "tag 索引", "source 字段 schema", "content 长度限制",
    "多语言支持", "CJK 字符分词", "全角/半角归一化", "标点符号过滤",
    "中文繁简归一化",
]

APPROVAL_THEMES = [
    "三级公立医院绩效考核批复", "区域医疗中心建设方案批复", "互联网医院设置批复",
    "医疗设备配置许可批复", "医保新增项目目录批复", "重大公共卫生事件应急响应批复",
    "药品集中采购结果批复", "健康产业园区规划批复", "医学重点学科建设批复",
    "远程医疗服务定价批复",
]


def _seeded_rng(seed: str) -> random.Random:
    """Deterministic RNG from string seed (so bootstrap is reproducible)."""
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


def _content_for(entity_type: EntityType, theme: str, idx: int) -> str:
    base = f"{theme} — 实施指引第 {idx} 号。"
    if entity_type == EntityType.POLICY:
        return f"【政策】{base} 适用范围: 全国各级卫生健康行政部门及医疗机构。有效期: 5 年。"
    if entity_type == EntityType.REGULATION:
        return f"【规程】{base} 适用对象: 各级各类医疗机构与卫生专业人员。"
    if entity_type == EntityType.ADR:
        return f"【ADR】{base} 决策依据: 系统规模、检索性能、可维护性、合规要求。备选方案: 见 ADR 详情。"
    if entity_type == EntityType.APPROVAL:
        return f"【批复】{base} 批复机关: 省级卫生健康委员会。办理时限: 20 个工作日。"
    return base


def seed_default_corpus(g: KnowledgeGraph) -> dict[str, int]:
    counts = {
        "policy": 2000,
        "regulation": 1500,
        "adr": 1000,
        "approval": 500,
    }

    # ---- 1. Create all entities ----
    by_type: dict[EntityType, list[str]] = {
        EntityType.POLICY: [],
        EntityType.REGULATION: [],
        EntityType.ADR: [],
        EntityType.APPROVAL: [],
    }
    type_to_prefix = {
        EntityType.POLICY: ("P", POLICY_THEMES),
        EntityType.REGULATION: ("R", REGULATION_THEMES),
        EntityType.ADR: ("A", ADR_THEMES),
        EntityType.APPROVAL: ("X", APPROVAL_THEMES),
    }

    for etype, (prefix, themes) in type_to_prefix.items():
        n = counts[etype.value]
        for i in range(n):
            theme = themes[i % len(themes)]
            sub_idx = i // len(themes) + 1
            eid = f"{prefix}-{i:05d}"
            title = f"{theme} ({sub_idx:02d})"
            content = _content_for(etype, theme, sub_idx)
            tags = [etype.value, theme.split()[0] if " " in theme else theme]
            g.add_entity(Entity(
                id=eid,
                entity_type=etype,
                title=title,
                content=content,
                source=f"https://kems.example.gov.cn/{etype.value}/{eid}",
                tags=tags,
            ))
            by_type[etype].append(eid)

    # ---- 2. Create edges to reach ≥20000 ----
    # 策略: 每个 policy 3-5 cites regulations, 每个 regulation 2-4 implements policies,
    # 每个 ADR 5-10 references 任意, 每个 approval 1-3 cites policies
    rng = _seeded_rng("kems-v2-bootstrap-v1")
    edge_count = 0

    def _add(source: str, target: str, rel: RelationType) -> None:
        nonlocal edge_count
        if source == target:
            return
        if g.get_entity(source) is None or g.get_entity(target) is None:
            return
        # 防重复
        for e in g._edges:
            if e.source_id == source and e.target_id == target and e.relation == rel:
                return
        g.add_edge(Edge(source_id=source, target_id=target, relation=rel))
        edge_count += 1

    # policy → regulation (cites), 3-5 per policy
    for pid in by_type[EntityType.POLICY]:
        rids = rng.sample(by_type[EntityType.REGULATION], rng.randint(3, 5))
        for rid in rids:
            _add(pid, rid, RelationType.CITES)

    # regulation → policy (implements), 2-4 per regulation
    for rid in by_type[EntityType.REGULATION]:
        pids = rng.sample(by_type[EntityType.POLICY], rng.randint(2, 4))
        for pid in pids:
            _add(rid, pid, RelationType.IMPLEMENTS)

    # ADR → 任意, 5-10 per ADR
    all_other = by_type[EntityType.POLICY] + by_type[EntityType.REGULATION] + by_type[EntityType.APPROVAL]
    for aid in by_type[EntityType.ADR]:
        targets = rng.sample(all_other, rng.randint(5, 10))
        for tid in targets:
            _add(aid, tid, RelationType.REFERENCES)

    # approval → policy (cites), 1-3 per approval
    for xid in by_type[EntityType.APPROVAL]:
        pids = rng.sample(by_type[EntityType.POLICY], rng.randint(1, 3))
        for pid in pids:
            _add(xid, pid, RelationType.CITES)

    # policy supersedes policy: 旧版 → 新版 (chain 同主题)
    for etype, (prefix, themes) in type_to_prefix.items():
        n = counts[etype.value]
        for i in range(n):
            if i >= len(themes):
                # 同主题前后链
                cur_id = f"{prefix}-{i:05d}"
                prev_id = f"{prefix}-{i - len(themes):05d}"
                if rng.random() < 0.3 and i > len(themes):
                    _add(cur_id, prev_id, RelationType.SUPERSEDES)

    return {**counts, "edges": edge_count}
