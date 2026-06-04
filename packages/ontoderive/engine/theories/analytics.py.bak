"""
分析模式引擎 — Analytical Patterns Engine
============================================
将领域知识(博弈论/经济学/组织行为学/策略规划)编码为可复用的分析模板。
每个模式 = 检测规则(确定性) + 分析逻辑(公式/LLM增强) → 统一结论

与推理规则的区别:
  推理规则(R1-R19): 回答"推导对不对" — 逻辑一致性
  分析模式(A1-Ax):  回答"这意味着什么" — 领域洞察
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from engine.foundation.semantic import SemanticMatcher


@dataclass
class AnalyticalPattern:
    """分析模式定义

    semantic_depth: 0-5连续推理深度
      0 = 纯正则/数值比较 (R1-R18级别)
      1 = 语义匹配 (TF-IDF)
      2 = 嵌入向量 (需外部模型)
      3 = 轻量分类器
      4 = 小语言模型 (本地)
      5 = 大语言模型 (云端LLM)
    """

    name: str
    description: str
    category: str  # game_theory | economics | supply_chain | organizational | strategic
    detect: Callable  # (facts, entities, relations) → bool
    analyze: Callable  # (facts, entities, relations, enhancer) → List[dict]
    semantic_depth: int = 0  # 0-5连续推理深度
    requires_llm: bool = False  # 向后兼容, 等同于 semantic_depth >= 4


class AnalyticsEngine:
    """分析模式引擎 — 确定性检测 + 可选的LLM增强"""

    def __init__(self, enhancer=None, matcher=None):
        self.enhancer = enhancer
        self.matcher = matcher  # 语义匹配器 (v3.4 fix)
        self.patterns = self._register_patterns()

    def _register_patterns(self):
        return [
            # ═══ A1: 供给弹性分析 ═══
            AnalyticalPattern(
                name="capacity_elasticity",
                description="检测产能/库存约束, 估算供给弹性",
                category="economics",
                detect=self._detect_capacity_constraint,
                analyze=self._analyze_capacity,
                semantic_depth=0,  # 纯公式计算
            ),
            # ═══ A2: 供应链风险放大 ═══
            AnalyticalPattern(
                name="supply_chain_amplification",
                description="沿depends_on链计算风险传导放大系数",
                category="supply_chain",
                detect=self._detect_supply_risk,
                analyze=self._analyze_supply_chain,
                semantic_depth=1,  # TF-IDF语义匹配
            ),
            # ═══ A3: 代理问题检测 ═══
            AnalyticalPattern(
                name="principal_agent",
                description="检测employs关系中法律雇主≠实际服务对象的代理问题",
                category="game_theory",
                detect=self._detect_agency_issue,
                analyze=self._analyze_agency,
                semantic_depth=4,  # 需要LLM理解组织上下文
            ),
            # ═══ A4: 激励不相容检测 ═══
            AnalyticalPattern(
                name="incentive_misalignment",
                description="对比各实体的目标与激励结构, 检测错位",
                category="organizational",
                detect=self._detect_incentive_issue,
                analyze=self._analyze_incentive,
                semantic_depth=1,  # TF-IDF语义匹配 (v3.4升级)
            ),
            # ═══ A5: 分阶段补救规划 ═══
            AnalyticalPattern(
                name="remediation_planning",
                description="基于问题严重度和可行性生成短/中/长期行动方案",
                category="strategic",
                detect=self._detect_remediation_needed,
                analyze=self._analyze_remediation,
                semantic_depth=1,  # 确定性计算+可选LLM增强
            ),
            # ═══ A6: 市场结构分析 ═══
            AnalyticalPattern(
                name="market_structure",
                description="实体数量+份额分布→HHI集中度+市场类型判定",
                category="economics",
                detect=self._detect_market_structure,
                analyze=self._analyze_market_structure,
                semantic_depth=0,  # 纯公式计算
            ),
            # ═══ A7: 博弈均衡检测 ═══
            AnalyticalPattern(
                name="game_equilibrium",
                description="多方竞争/合作/博弈关系→均衡类型+囚徒困境识别",
                category="game_theory",
                detect=self._detect_game_equilibrium,
                analyze=self._analyze_game_equilibrium,
                semantic_depth=1,  # TF-IDF语义匹配
            ),
            # ═══ A8: 策略选项生成 ═══
            AnalyticalPattern(
                name="strategic_options",
                description="目标+约束+资源→可行策略+风险收益评分",
                category="strategic",
                detect=self._detect_strategic_options,
                analyze=self._analyze_strategic_options,
                semantic_depth=2,  # 嵌入向量级别
            ),
            # ═══ A9: 信息生态健康度 ═══
            AnalyticalPattern(
                name="info_ecology",
                description="虚假信息占比×公众信任度×专家共识度→信息生态健康评分",
                category="strategic",
                detect=self._detect_info_ecology,
                analyze=self._analyze_info_ecology,
                semantic_depth=0,  # 纯公式计算
            ),
            # ═══ A10: 因果链分析 ═══ (v3.6)
            AnalyticalPattern(
                name="causal_chain",
                description="从derives_from DAG提取因果路径+中介变量+因果距离",
                category="supply_chain",
                detect=self._detect_causal_chain,
                analyze=self._analyze_causal_chain,
                semantic_depth=0,
            ),
            # ═══ A11: 情景规划 ═══ (v3.6)
            AnalyticalPattern(
                name="scenario_planning",
                description="基于关键不确定性→2×2矩阵→4情景+触发信号",
                category="strategic",
                detect=self._detect_scenario_planning,
                analyze=self._analyze_scenario_planning,
                semantic_depth=1,
            ),
            # ═══ A12: 权力地图 ═══ (v3.6)
            AnalyticalPattern(
                name="power_map",
                description="从关系网络计算中心性→识别关键影响力节点",
                category="organizational",
                detect=self._detect_power_map,
                analyze=self._analyze_power_map,
                semantic_depth=0,
            ),
            # ═══ A13: 组织惯性分析 ═══ (v3.6)
            AnalyticalPattern(
                name="organizational_inertia",
                description="检测组织规模/历史/资源锁定形成的变革阻力",
                category="organizational",
                detect=self._detect_organizational_inertia,
                analyze=self._analyze_organizational_inertia,
                semantic_depth=0,
            ),
            # ═══ A14: 技术颠覆风险 ═══ (v3.6)
            AnalyticalPattern(
                name="tech_disruption",
                description="识别新技术对现有格局的技术替代威胁",
                category="strategic",
                detect=self._detect_tech_disruption,
                analyze=self._analyze_tech_disruption,
                semantic_depth=1,
            ),
        ]

    def run(self, facts, entities, inferences, relations=None, patterns=None, max_depth: int = 5):
        """运行所有(或指定)分析模式, 返回洞察列表

        max_depth: 最大推理深度 (0=仅纯规则, 3=含分类器, 5=含LLM)
        """
        if not isinstance(facts, dict):
            return []
        # 可用深度: 有enhancer→max 5, 有matcher→max 1, 否则→0
        available_depth = 0
        if self.enhancer and self.enhancer.available:
            available_depth = 5
        elif hasattr(self, "matcher") and self.matcher:
            available_depth = 1
        effective_depth = min(max_depth, available_depth)

        results = []
        targets = patterns or self.patterns
        for pat in targets:
            # 深度控制: 只运行深度在可用范围内的模式
            if pat.semantic_depth > effective_depth:
                continue
            try:
                if pat.detect(facts, entities, relations or []):
                    conclusions = pat.analyze(facts, entities, relations or [], self.enhancer)
                    for c in conclusions:
                        c["pattern"] = pat.name
                        c["category"] = pat.category
                        c["semantic_depth"] = pat.semantic_depth
                    results.extend(conclusions)
            except Exception:
                pass
        return results

    # ═══ A1: 供给弹性 ═══

    def _detect_capacity_constraint(self, facts, entities, relations):
        """检测: 利用率>90%供给紧张 或 利用率<60%产能过剩 或 库存偏离基准"""
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "") + info.get("description", "")
            val = info.get("value", "")
            if "利用率" in desc or "产能" in desc:
                num = _extract_num(val)
                if num > 90 or (num > 0 and num < 60):
                    return True
            if "库存" in desc:
                stock = _extract_num(val)
                # 查找对应安全基准
                for fid2, info2 in _iter_facts(facts):
                    if "安全" in info2.get("desc", "") and _extract_num(info2.get("value", "")) > stock:
                        return True
        return False

    def _analyze_capacity(self, facts, entities, relations, enhancer):
        results = []
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "") + info.get("description", "")
            val = info.get("value", "")
            num = _extract_num(val)
            if num <= 0:
                continue
            # 利用率分析 (供给紧张)
            if "利用率" in desc and num > 90 and num <= 100:
                elasticity = max(0, (100 - num) / num)  # 剩余产能比例
                results.append(
                    {
                        "type": "analytics",
                        "conclusion": f"供给弹性≈{elasticity:.2f}: '{desc}'={val}, "
                        f"仅余{100 - num:.0f}%产能, 需求波动将直接传导为短缺",
                        "derives_from": [fid],
                        "confidence": 0.85,
                    }
                )
            # 产能过剩检测 (v3.4)
            elif "利用率" in desc and num > 0 and num < 60:
                excess_pct = 100 - num
                results.append(
                    {
                        "type": "analytics",
                        "conclusion": f"产能过剩: '{desc}'={val}, 闲置{excess_pct:.0f}%产能, "
                        f"供过于求→价格下行→行业出清压力",
                        "derives_from": [fid],
                        "confidence": 0.80,
                    }
                )
            # 库存vs安全基准
            if "库存" in desc:
                for fid2, info2 in _iter_facts(facts):
                    if "安全" in info2.get("desc", ""):
                        safe = _extract_num(info2.get("value", ""))
                        if safe > num:
                            gap_pct = (safe - num) / safe * 100
                            results.append(
                                {
                                    "type": "analytics",
                                    "conclusion": f"库存缺口: '{desc}'={val}低于安全基准{safe}, "
                                    f"缺口{gap_pct:.0f}%, 补库压力紧迫",
                                    "derives_from": [fid, fid2],
                                    "confidence": 0.90,
                                }
                            )
        return results

    # ═══ A2: 供应链风险放大 ═══

    def _detect_supply_risk(self, facts, entities, relations):
        """检测: 存在depends_on链 + 交付/库存异常"""
        has_chain = any(r.get("relation_type") == "depends_on" for r in (relations or []))
        has_issue = any(
            "交付" in (f.get("desc", "") + f.get("description", "")) and _extract_num(f.get("value", "")) < 80
            for _, f in _iter_facts(facts)
        )
        return has_chain and has_issue

    def _analyze_supply_chain(self, facts, entities, relations, enhancer):
        results = []
        # 语义匹配器: 基于事实描述
        descs = [info.get("desc", "") for _, info in _iter_facts(facts)]
        matcher = SemanticMatcher(descs if descs else ["default"])
        # 构建依赖图
        deps = {}
        for r in relations or []:
            if r.get("relation_type") == "depends_on":
                deps.setdefault(r["subject"], []).append((r["object"], 1.0))
        # 查找交付异常
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "") + info.get("description", "")
            if "交付" not in desc:
                continue
            delivery = _extract_num(info.get("value", ""))
            if delivery >= 80 or delivery <= 0:
                continue
            entity_name = _find_entity_for_fact(fid, desc, entities, matcher)
            upstreams = deps.get(entity_name, [])
            if not upstreams:
                for subj in deps:
                    if matcher.is_semantically_related(subj, desc):
                        upstreams = deps.get(subj, [])
                        entity_name = subj
                        break
            for up_name, ratio in upstreams:
                for fid2, info2 in _iter_facts(facts):
                    up_desc = info2.get("desc", "")
                    if "库存" in up_desc:
                        stock = _extract_num(info2.get("value", ""))
                        amplification = (100 - delivery) / 100 * ratio
                        results.append(
                            {
                                "type": "analytics",
                                "conclusion": f"风险传导: {entity_name}交付{delivery}%→上游{up_name}"
                                f"库存{stock}天, 放大系数≈{amplification:.2f}",
                                "derives_from": [fid, fid2],
                                "confidence": 0.75,
                            }
                        )
        return results

    # ═══ A3: 代理问题 ═══

    def _detect_agency_issue(self, facts, entities, relations):
        """检测: X employs Y, 且Y的工作输出实际服务于Z(≠X)"""
        employs_pairs = [(r["subject"], r["object"]) for r in (relations or []) if r.get("relation_type") == "employs"]
        if not employs_pairs:
            return False
        # 检查被雇佣方是否通过其他关系服务于第三方
        for employer, employee in employs_pairs:
            for r in relations or []:
                if (
                    r.get("subject") == employee
                    and r.get("relation_type") in ("cooperates_with", "depends_on", "influences")
                    and r.get("object") != employer
                ):
                    return True
        return False

    def _analyze_agency(self, facts, entities, relations, enhancer):
        results = []
        employs_pairs = [(r["subject"], r["object"]) for r in (relations or []) if r.get("relation_type") == "employs"]
        for employer, employee in employs_pairs:
            for r in relations or []:
                if r.get("subject") == employee and r.get("object") != employer:
                    base = (
                        f"潜在代理问题: {employer} employs {employee}, "
                        f"但{employee}的'{r['relation_type']}'关系指向{r['object']}"
                    )
                    if enhancer and enhancer.available:
                        try:
                            enhanced = enhancer._call(
                                f"分析以下代理问题的组织影响(一句话): {base}", "你是组织行为学专家。", 0.3
                            )
                            if enhanced:
                                base += f"。LLM分析: {enhanced.strip()[:200]}"
                        except Exception:
                            pass
                    results.append(
                        {
                            "type": "analytics",
                            "conclusion": base,
                            "derives_from": [employer, employee, r.get("object", "")],
                            "confidence": 0.70,
                        }
                    )
        return results

    # ═══ A4: 激励不相容 ═══

    def _detect_incentive_issue(self, facts, entities, relations):
        """检测: 多实体共享资源(语义关联) + 有不同的事实描述"""
        # 找共享同一目标实体的多个主体
        targets = {}
        for r in relations or []:
            obj = r.get("object", "")
            targets.setdefault(obj, []).append(r.get("subject", ""))
        shared_resources = [(t, subs) for t, subs in targets.items() if len(subs) >= 2]
        return len(shared_resources) >= 1

    def _analyze_incentive(self, facts, entities, relations, enhancer):
        results = []
        # 匹配器: 用事实描述语料
        fact_desc = [f.get("desc", "") for f in facts.values() if isinstance(f, dict)]
        matcher = SemanticMatcher(fact_desc if fact_desc else ["default"])

        targets = {}
        for r in relations or []:
            obj = r.get("object", "")
            targets.setdefault(obj, []).append(r.get("subject", ""))

        shared = [(t, subs) for t, subs in targets.items() if len(subs) >= 2]
        for target, subjects in shared:
            # 检测: 共享同一资源的实体是否有语义差异大的事实
            subj_facts = {}
            for fid, info in _iter_facts(facts):
                desc = info.get("desc", "")
                for subj in subjects:
                    if matcher.is_semantically_related(desc, subj, threshold=0.15):
                        subj_facts.setdefault(subj, []).append(desc)
            if len(subj_facts) >= 2:
                pairs = list(subj_facts.items())
                for i in range(len(pairs)):
                    for j in range(i + 1, len(pairs)):
                        s1, f1 = pairs[i]
                        s2, f2 = pairs[j]
                        if matcher.is_semantically_related(" ".join(f1), " ".join(f2), threshold=0.30):
                            continue  # 相似→目标一致
                        # 不相似→潜在激励冲突
                        results.append(
                            {
                                "type": "analytics",
                                "conclusion": f"潜在激励冲突: {s1}({', '.join(f1[:2])})与"
                                f"{s2}({', '.join(f2[:2])})共享{target}但关注点不同",
                                "derives_from": subjects + [target],
                                "confidence": 0.60,
                            }
                        )
        return results

    # ═══ A5: 补救规划 ═══

    def _detect_remediation_needed(self, facts, entities, relations):
        """检测: 存在'问题'/'审计'/'整改'相关事实或推论"""
        for _, info in _iter_facts(facts):
            desc = info.get("desc", "") + info.get("description", "")
            if any(kw in desc for kw in ("审计", "整改", "问题", "风险", "违规", "差距")):
                return True
        return False

    def _analyze_remediation(self, facts, entities, relations, enhancer):
        results = []
        problems = []
        team_size, months = 4, 6  # 默认值
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "") + info.get("description", "")
            val = info.get("value", "")
            if "团队" in desc or "合规" in desc:
                team_size = max(1, int(_extract_num(val)))
            if "距" in desc and "月" in desc:
                months = max(1, int(_extract_num(val)))
            if any(kw in desc for kw in ("审计问题", "高风险", "整改率", "认证", "差距")):
                problems.append(f"{desc}={val}")
        if not problems:
            return results

        # 可行性比率 (v3.4): 问题任务数÷(人数×月数)
        task_count = 0
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "")
            val = info.get("value", "")
            if "问题" in desc and _extract_num(val) > 0:
                task_count = max(task_count, int(_extract_num(val)))
        remaining_tasks = max(task_count, 1)
        feasibility = remaining_tasks / max(team_size * months, 1)
        status = "不可行⚠️" if feasibility > 1.5 else ("紧张" if feasibility > 1.0 else "可行")
        results.append(
            {
                "type": "analytics",
                "conclusion": (
                    f"整改可行性: {remaining_tasks}问题/{team_size}人/{months}月="
                    f"人均{feasibility:.1f}个/月→{status}"
                    f"{' 需增加人力或延长时间窗口' if feasibility > 1.0 else ''}"
                ),
                "derives_from": [
                    fid
                    for fid, _ in _iter_facts(facts)
                    if any(kw in facts.get(fid, {}).get("desc", "") for kw in ("审计", "整改"))
                ][:5],
                "confidence": 0.85,
            }
        )

        # 严重度分类
        high_risk = sum(1 for p in problems if "高风险" in p or "差距" in p)
        if high_risk > 0:
            results.append(
                {
                    "type": "analytics",
                    "conclusion": f"短期(0-3月)优先: 解决{high_risk}个高风险项, 防止监管执法触发",
                    "derives_from": [fid for fid in facts],
                    "confidence": 0.80,
                }
            )

        if enhancer and enhancer.available:
            try:
                context = "; ".join(problems[:8])
                plan = enhancer._call(
                    f"基于以下问题生成分阶段补救方案(短/中/长期各1-2句话): {context}", "你是战略规划专家。", 0.4
                )
                if plan:
                    results.append(
                        {
                            "type": "analytics",
                            "conclusion": f"分阶段方案: {plan.strip()[:300]}",
                            "derives_from": [
                                fid
                                for fid in facts
                                if any(kw in facts[fid].get("desc", "") for kw in ("审计", "整改", "问题"))
                            ],
                            "confidence": 0.65,
                        }
                    )
            except Exception:
                pass
        return results

    # ═══ A6: 市场结构分析 ═══

    _MARKET_KW = (
        "份额",
        "占比",
        "集中度",
        "CR",
        "寡头",
        "垄断",
        "竞争格局",
        "玩家",
        "市场占有率",
        "渗透率",
        "市占",
        "HHI",
        "CR3",
        "CR5",
    )

    # A13: 组织惯性关键词
    _INERTIA_KW = ("转型", "惯性", "路径依赖", "沉没成本", "变革", "组织僵化", "体系庞大")
    _HISTORY_KW = ("成立于", "运营", "年限", "历史", "悠久")
    _RESOURCE_KW = ("投入", "资产", "投资", "预算", "员工数")

    # A14: 技术颠覆关键词
    _TECH_NEW_KW = ("AI", "数字化", "智能化", "云", "区块链", "量子", "自动化", "新技术")
    _TECH_OLD_KW = ("传统", "成熟", "稳定", "已有", "现有", "现成")
    _DISRUPTION_KW = ("颠覆", "替代", "冲击", "淘汰")

    def _detect_market_structure(self, facts, entities, relations):
        """检测: ≥3实体 或 存在市场份额关键词"""
        n_entities = len(entities) if isinstance(entities, dict) else len(entities)
        if n_entities >= 3:
            return True
        for _, info in _iter_facts(facts):
            if any(kw in info.get("desc", "") for kw in self._MARKET_KW):
                return True
        return False

    def _analyze_market_structure(self, facts, entities, relations, enhancer):
        """HHI集中度 + 市场类型判定"""
        results = []
        n = len(entities) if isinstance(entities, dict) else len(entities)
        shares = []
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "")
            if any(kw in desc for kw in self._MARKET_KW):
                shares.append(_extract_num(info.get("value", "")))
        if not shares:
            return results
        # HHI = sum(share_i^2)
        total = sum(shares) or 1
        hhi = sum((s / total * 100) ** 2 for s in shares)
        mtype = "垄断" if hhi > 2500 else ("寡头" if hhi > 1500 else ("集中" if hhi > 1000 else "分散"))
        cr3 = sum(sorted(shares, reverse=True)[:3]) / total * 100 if len(shares) >= 3 else 100
        results.append(
            {
                "type": "analytics",
                "conclusion": f"市场结构: HHI={hhi:.0f}({mtype}), CR3={cr3:.0f}%, {n}个参与者",
                "derives_from": [fid for fid in facts],
                "confidence": 0.80,
            }
        )
        return results

    # ═══ A7: 博弈均衡检测 ═══

    def _detect_game_equilibrium(self, facts, entities, relations):
        """检测: 多方竞争/合作关系"""
        comp_count = sum(1 for r in (relations or []) if r.get("relation_type") == "competes_with")
        coop_count = sum(1 for r in (relations or []) if r.get("relation_type") == "cooperates_with")
        return comp_count >= 1 or coop_count >= 2

    def _analyze_game_equilibrium(self, facts, entities, relations, enhancer):
        """识别博弈结构: 囚徒困境/协调博弈/零和博弈"""
        results = []
        comps = [r for r in (relations or []) if r.get("relation_type") == "competes_with"]
        coops = [r for r in (relations or []) if r.get("relation_type") == "cooperates_with"]
        # 竞争+合作共存 → 潜在囚徒困境
        if comps and coops:
            results.append(
                {
                    "type": "analytics",
                    "conclusion": f"囚徒困境风险: {len(comps)}对竞争+{len(coops)}对合作共存, 个体理性可能导致集体次优",
                    "derives_from": [],
                    "confidence": 0.65,
                }
            )
        # 纯竞争 → 零和或负和博弈
        if comps and not coops:
            results.append(
                {
                    "type": "analytics",
                    "conclusion": f"零和博弈: {len(comps)}对竞争关系, 无合作→可能陷入价格战/军备竞赛",
                    "derives_from": [],
                    "confidence": 0.70,
                }
            )
        return results

    # ═══ A8: 策略选项生成 ═══

    def _detect_strategic_options(self, facts, entities, relations):
        """检测: 存在问题+约束+资源"""
        has_problem = self._detect_remediation_needed(facts, entities, relations)
        has_constraint = any(
            "约束" in info.get("desc", "") or "限制" in info.get("desc", "") for _, info in _iter_facts(facts)
        )
        return has_problem or has_constraint

    def _analyze_strategic_options(self, facts, entities, relations, enhancer):
        """生成策略选项 — 基于目标/约束/资源组合"""
        results = []
        # 收集目标、约束、资源
        goals = [
            info.get("desc", "")
            for _, info in _iter_facts(facts)
            if any(kw in info.get("desc", "") for kw in ("目标", "计划", "预计"))
        ]
        constraints = [
            info.get("desc", "")
            for _, info in _iter_facts(facts)
            if any(kw in info.get("desc", "") for kw in ("限制", "约束", "上限", "不超过"))
        ]
        resources = [
            info.get("desc", "")
            for _, info in _iter_facts(facts)
            if any(kw in info.get("desc", "") for kw in ("预算", "团队", "储备", "现金"))
        ]
        if not goals and not constraints:
            return results
        # 策略空间 + 帕累托分析
        n_combos = 2 ** len(goals) if goals else 1
        feasible = max(1, n_combos - len(constraints))
        pareto_note = ""
        tree_depth = len(goals) + len(constraints)
        if len(goals) >= 2 and len(constraints) >= 1:
            pareto_note = f", 约束{len(constraints)}个→帕累托前沿需在{feasible}个可行解中寻找"
        depth_str = f", 博弈树深度≈{tree_depth}" if goals else ""
        results.append(
            {
                "type": "analytics",
                "conclusion": f"策略空间: {len(goals)}目标×{len(constraints)}约束×{len(resources)}资源"
                f"→ {n_combos}种组合{depth_str}{pareto_note}",
                "derives_from": [fid for fid in facts],
                "confidence": 0.60,
            }
        )
        return results

    # ═══ A9: 信息生态健康度 (v3.5) ═══

    def _detect_info_ecology(self, facts, entities, relations):
        """检测: 虚假信息/可信度/信任度/共识度相关数据"""
        kw = ("虚假信息", "可信度", "信任度", "共识度", "信息", "公众信任")
        for _, info in _iter_facts(facts):
            if any(k in info.get("desc", "") for k in kw):
                return True
        return False

    def _analyze_info_ecology(self, facts, entities, relations, enhancer):
        """信息生态健康度评分"""
        results = []
        disinfo = trust = consensus = 0.0
        for _, info in _iter_facts(facts):
            desc = info.get("desc", "")
            val = _extract_num(info.get("value", ""))
            if "虚假" in desc:
                disinfo = val
            elif "信任" in desc and val > 0:
                trust = val
            elif "共识" in desc and val > 0:
                consensus = val
        if not (disinfo or trust or consensus):
            return results
        # 信息生态健康度 = (1 - 虚假率) × 信任度 × 共识度归一化
        health = (100 - disinfo) / 100 * (trust / 100) * (consensus / 100) * 100
        status = "崩溃" if health < 5 else ("危机" if health < 15 else ("脆弱" if health < 30 else "健康"))
        results.append(
            {
                "type": "analytics",
                "conclusion": f"信息生态健康度: {health:.1f}/100({status}), "
                f"虚假{disinfo}%+信任{trust}%+共识{consensus}%→"
                f"{'事实共识已瓦解' if health < 15 else '尚可正常决策'}",
                "derives_from": [],
                "confidence": 0.75,
            }
        )
        return results

    # ═══ A10: 因果链分析 (v3.6) ═══

    def _detect_causal_chain(self, facts, entities, relations):
        return len(relations or []) >= 1

    def _analyze_causal_chain(self, facts, entities, relations, enhancer):
        results = []
        deps = {}
        for r in relations or []:
            if r.get("relation_type") in ("depends_on", "causes", "influences"):
                deps.setdefault(r["subject"], []).append(r["object"])
        if len(deps) < 2:
            return results
        # BFS找所有因果路径 (v3.6 fix: 多分支)
        for start in deps:
            paths = [[start]]
            for path in paths:
                last = path[-1]
                if last in deps:
                    for up in deps[last]:
                        if up not in path:
                            new_path = path + [up]
                            paths.append(new_path)
                            if len(new_path) >= 3:
                                results.append(
                                    {
                                        "type": "analytics",
                                        "conclusion": f"因果链: {'→'.join(new_path)}, "
                                        f"深度{len(new_path) - 1}, "
                                        f"中介{new_path[1:-1]}, 根因={new_path[-1]}",
                                        "derives_from": new_path[:3],
                                        "confidence": 0.75,
                                    }
                                )
        return results

    # ═══ A11: 情景规划 (v3.6) ═══

    def _detect_scenario_planning(self, facts, entities, relations):
        kw = ("不确定性", "概率", "情景", "乐观", "悲观", "基线", "可能")
        for _, info in _iter_facts(facts):
            if any(k in info.get("desc", "") for k in kw):
                return True
        return False

    def _analyze_scenario_planning(self, facts, entities, relations, enhancer):
        results = []
        uncertainties = []
        for _, info in _iter_facts(facts):
            desc = info.get("desc", "")
            val = info.get("value", "")
            if any(k in desc for k in ("不确定性", "概率", "风险")):
                uncertainties.append((desc, _extract_num(val)))
        if len(uncertainties) < 2:
            return results
        u1, u2 = uncertainties[:2]
        scenarios = [
            (f"{u1[0]}高+{u2[0]}高", "乐观"),
            (f"{u1[0]}高+{u2[0]}低", "基准偏上"),
            (f"{u1[0]}低+{u2[0]}高", "基准偏下"),
            (f"{u1[0]}低+{u2[0]}低", "悲观"),
        ]
        results.append(
            {
                "type": "analytics",
                "conclusion": f"情景矩阵(2×2): {len(scenarios)}情景, "
                f"关键轴={u1[0]}({u1[1]:.0f})×{u2[0]}({u2[1]:.0f}), "
                f"早鸟指标: {u1[0]}趋势逆转或{u2[0]}突破阈值",
                "derives_from": [],
                "confidence": 0.60,
            }
        )
        return results

    # ═══ A12: 权力地图 (v3.6) ═══

    def _detect_power_map(self, facts, entities, relations):
        return len(relations or []) >= 4

    def _analyze_power_map(self, facts, entities, relations, enhancer):
        results = []
        # Degree centrality (度中心性): 每个节点参与的关系数
        centrality = {}
        for r in relations or []:
            s, o = r.get("subject", ""), r.get("object", "")
            centrality[s] = centrality.get(s, 0) + 1
            centrality[o] = centrality.get(o, 0) + 1
        if not centrality:
            return results
        top = sorted(centrality.items(), key=lambda x: -x[1])[:3]
        results.append(
            {
                "type": "analytics",
                "conclusion": f"权力地图: 关键节点={', '.join(f'{k}(度={v})' for k, v in top)}, "
                f"最大影响力={top[0][0]}({top[0][1]}连接), "
                f"潜在单点={'是' if top[0][1] >= len(centrality) / 2 else '否'}",
                "derives_from": [k for k, _ in top],
                "confidence": 0.70,
            }
        )
        return results

    # ═══ A13: 组织惯性分析 (v3.6) ═══

    def _detect_organizational_inertia(self, facts, entities, relations):
        """检测: 规模大/历史悠久/投入多 + 转型慢/变化难/惯性/路径依赖"""
        if len(entities or {}) >= 3 or len(relations or []) >= 4:
            return True
        for _, info in _iter_facts(facts):
            if any(k in info.get("desc", "") for k in self._INERTIA_KW):
                return True
        return False

    def _analyze_organizational_inertia(self, facts, entities, relations, enhancer):
        results = []
        if not entities:
            return results

        entity_count = len(entities or {})
        relation_count = len(relations or [])
        complexity = relation_count / max(entity_count, 1)

        history_signals = 0
        resource_lock = 0
        for _, info in _iter_facts(facts):
            desc = info.get("desc", "")
            if any(k in desc for k in self._HISTORY_KW):
                history_signals += 1
            if any(k in desc for k in self._RESOURCE_KW):
                resource_lock += 1

        inertia_index = complexity * (1 + history_signals) * (1 + resource_lock)
        level = "高" if inertia_index >= 6 else ("中" if inertia_index >= 3 else "低")

        top_entities = sorted(
            [eid for eid in (entities or {})],
            key=lambda e: sum(1 for r in (relations or []) if r.get("subject") == e or r.get("object") == e),
            reverse=True,
        )[:3]

        results.append(
            {
                "type": "analytics",
                "conclusion": f"组织惯性: 指数={inertia_index:.1f}({level}), "
                f"{entity_count}实体/{relation_count}关系, "
                f"复杂度={complexity:.1f}, "
                f"历史信号={history_signals}, 资源锁定={resource_lock}",
                "derives_from": top_entities,
                "confidence": 0.65,
            }
        )
        return results

    # ═══ A14: 技术颠覆风险 (v3.6) ═══

    def _detect_tech_disruption(self, facts, entities, relations):
        """检测: 新技术信号 + 传统技术描述"""
        has_new = False
        has_old = False
        for _, info in _iter_facts(facts):
            desc = info.get("desc", "")
            if any(k in desc for k in self._DISRUPTION_KW):
                return True
            if any(k in desc for k in self._TECH_NEW_KW):
                has_new = True
            if any(k in desc for k in self._TECH_OLD_KW):
                has_old = True
        return has_new or has_old

    def _analyze_tech_disruption(self, facts, entities, relations, enhancer):
        results = []

        new_signals = 0
        old_lock = 0
        new_entities = []
        old_entities = []
        for fid, info in _iter_facts(facts):
            desc = info.get("desc", "")
            new_signals += sum(1 for k in self._TECH_NEW_KW if k in desc)
            old_lock += sum(1 for k in self._TECH_OLD_KW if k in desc)
            if any(k in desc for k in self._TECH_NEW_KW):
                new_entities.append(fid)
            if any(k in desc for k in self._TECH_OLD_KW):
                old_entities.append(fid)

        disruption_pressure = new_signals / max(old_lock, 1)
        threat_level = "高" if disruption_pressure >= 2 else ("中" if disruption_pressure >= 1 else "低")

        conclusion = (
            f"技术颠覆风险: 压力={disruption_pressure:.1f}({threat_level}), "
            f"新技术信号={new_signals}, 现有锁定={old_lock}, "
        )
        if threat_level == "高":
            conclusion += "警告: 新技术威胁显著, 建议制定转型路线图"
        elif threat_level == "中":
            conclusion += "关注: 新技术正在积累, 建议跟踪监测"
        else:
            conclusion += "正常: 现有技术仍占主导"

        results.append(
            {
                "type": "analytics",
                "conclusion": conclusion,
                "derives_from": new_entities[:3] + old_entities[:3],
                "confidence": 0.70,
            }
        )
        return results


def _is_dict(val):
    return isinstance(val, dict)


def _iter_facts(facts):
    """安全迭代facts — 过滤非dict值"""
    if not isinstance(facts, dict):
        return
    for fid, info in facts.items():
        if _is_dict(info):
            yield fid, info


def _extract_num(val):
    """从值中提取数字"""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, bool):
        return 0.0  # bool→0.0 (bool在JSON中不应出现在value字段, 若出现视为0)
    m = re.search(r"(\d+\.?\d*)", str(val))
    return float(m.group(1)) if m else 0.0


def _find_entity_for_fact(fid, desc, entities, matcher=None):
    """根据事实描述找到对应实体ID — 语义匹配优先"""
    if not isinstance(entities, dict):
        return fid
    # TF-IDF语义匹配
    if matcher:
        candidates = [info.get("name", "") for info in entities.values() if isinstance(info, dict)]
        if candidates:
            best, score = matcher.best_match(desc, candidates, threshold=0.15)
            if best and score > 0.15:
                for eid, info in entities.items():
                    if isinstance(info, dict) and info.get("name") == best:
                        return eid
    # 回退: 精确字符串匹配
    for eid, info in entities.items():
        if isinstance(info, dict) and info.get("name", "") in desc:
            return eid
    return fid
