from __future__ import annotations

"""
---
Type: Organ
Status: Active
Layer: D-Governance
Owner: '@Prime'
Constraint: '[!!] AI_ASSISTED_DECISION'
Summary: AIAssistedCommittee — AI辅助的委员会决策，提供智能建议和预测
Tags:
- ai
- committee
- decision-support
- prediction
- nlp
Authority: docs/improvement_plan_unified.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Ai Assisted Committee ≡ Module
# 内涵 ≝ {Ai, Assisted, Committee}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, AiAssistedCommittee)}
# 功能 ⊢ {Ai_Assisted, Assisted_Committee, Committee_Init}
# =============================================================================

import time
from dataclasses import dataclass


@dataclass
class ProposalAnalysis:
    """提案分析结果"""

    proposal_id: str
    complexity_score: float  # 0-1
    risk_score: float  # 0-1
    impact_score: float  # 0-1
    estimated_discussion_time: int  # 分钟
    recommended_members: list[str]
    similar_past_proposals: list[str]
    suggested_questions: list[str]
    predicted_outcome: str  # "approve", "reject", "defer"
    confidence: float


@dataclass
class VoteRecommendation:
    """投票建议"""

    member: str
    recommendation: str  # "approve", "reject", "abstain"
    reasoning: str
    confidence: float
    key_considerations: list[str]


class AIAssistedCommittee:
    """AI辅助委员会

    核心能力:
    - 提案复杂度自动分析
    - 历史相似提案检索
    - 投票倾向预测
    - 讨论时间估计
    - 智能问答建议
    """

    def __init__(self) -> None:
        # 提案历史库
        self._proposal_history: list[dict] = []

        # 成员投票历史
        self._member_voting_patterns: dict[str, dict] = {}

        # 关键词风险库
        self._risk_keywords = {
            "high": ["security", "breaking", "fundamental", "architecture"],
            "medium": ["performance", "optimization", "refactor"],
            "low": ["documentation", "style", "comment"],
        }

    def analyze_proposal(self, proposal_id: str, content: str, proposer: str) -> ProposalAnalysis:
        """分析提案"""
        content_lower = content.lower()

        # 复杂度分析 (基于关键词密度和长度)
        word_count = len(content.split())
        complexity = min(word_count / 500, 1.0)  # 500词以上为最高复杂度

        # 风险分析
        risk_score = 0.0
        for keyword in self._risk_keywords["high"]:
            if keyword in content_lower:
                risk_score += 0.3
        for keyword in self._risk_keywords["medium"]:
            if keyword in content_lower:
                risk_score += 0.15
        risk_score = min(risk_score, 1.0)

        # 影响分析 (基于涉及域的数量)
        domains_mentioned = []
        for domain in ["D-Memory", "D-Economy", "D-Execution", "D-Governance", "D-Monitoring"]:
            if domain.lower().replace("d-", "") in content_lower:
                domains_mentioned.append(domain)
        impact_score = min(len(domains_mentioned) / 5, 1.0)

        # 估计讨论时间
        base_time = 10  # 基础10分钟
        complexity_time = complexity * 30  # 复杂度增加最多30分钟
        risk_time = risk_score * 20  # 风险增加最多20分钟
        estimated_time = int(base_time + complexity_time + risk_time)

        # 推荐委员 (基于专业领域匹配)
        recommended_members = self._recommend_members(content, domains_mentioned)

        # 查找相似历史提案
        similar = self._find_similar_proposals(content)

        # 预测结果
        predicted, confidence = self._predict_outcome(content, similar)

        # 建议问题
        questions = self._suggest_questions(content, risk_score)

        analysis = ProposalAnalysis(
            proposal_id=proposal_id,
            complexity_score=complexity,
            risk_score=risk_score,
            impact_score=impact_score,
            estimated_discussion_time=estimated_time,
            recommended_members=recommended_members,
            similar_past_proposals=similar,
            suggested_questions=questions,
            predicted_outcome=predicted,
            confidence=confidence,
        )

        # 存储到历史
        self._proposal_history.append(
            {
                "id": proposal_id,
                "content": content,
                "analysis": analysis,
                "timestamp": time.time(),
            }
        )

        return analysis

    def _recommend_members(self, content: str, domains: list[str]) -> list[str]:
        """推荐委员"""
        recommendations = []

        # 基于域匹配
        domain_experts = {
            "D-Memory": "@Nyx",
            "D-Economy": "@Builder",
            "D-Execution": "@Prime",
            "D-Governance": "@Sage",
            "D-Monitoring": "@Omega",
        }

        for domain in domains:
            if domain in domain_experts:
                recommendations.append(domain_experts[domain])

        # 基于历史参与度
        recommendations.append("@Devil")  # 风险审查专家

        return list(set(recommendations))

    def _find_similar_proposals(self, content: str) -> list[str]:
        """查找相似提案"""
        # 简化实现：基于关键词匹配
        content_keywords = set(content.lower().split())
        similar = []

        for past in self._proposal_history[-10:]:  # 只检查最近10个
            past_keywords = set(past["content"].lower().split())
            overlap = len(content_keywords & past_keywords)
            if overlap > 5:  # 至少5个共同词
                similar.append(past["id"])

        return similar[:3]  # 最多返回3个

    def _predict_outcome(self, content: str, similar: list[str]) -> tuple[str, float]:
        """预测结果"""
        if not similar:
            return "defer", 0.5

        # 基于相似提案的历史结果
        # 简化实现：假设通过率高
        return "approve", 0.75

    def _suggest_questions(self, content: str, risk_score: float) -> list[str]:
        """建议问题"""
        questions = []

        if risk_score > 0.5:
            questions.append("What is the rollback plan if this change causes issues?")
            questions.append("Have we tested this in a staging environment?")

        if "performance" in content.lower():
            questions.append("What are the expected performance improvements?")
            questions.append("How will we measure the impact?")

        if "security" in content.lower():
            questions.append("Has this been reviewed by the security team?")
            questions.append("Are there any new attack vectors introduced?")

        if not questions:
            questions.append("Can you provide more details on the implementation approach?")

        return questions

    def recommend_vote(self, member: str, proposal_id: str, proposal_content: str) -> VoteRecommendation:
        """推荐投票"""
        # 简化实现：基于角色推荐
        if member == "@Devil":
            recommendation = "reject" if "risk" in proposal_content.lower() else "approve"
            reasoning = "As risk reviewer, I need to ensure all edge cases are covered."
        elif member == "@Sage":
            recommendation = "approve"
            reasoning = "This aligns with our long-term architectural goals."
        elif member == "@Builder":
            recommendation = "approve"
            reasoning = "Implementation is feasible and well-scoped."
        else:
            recommendation = "approve"
            reasoning = "The proposal is well-documented and addresses a real need."

        return VoteRecommendation(
            member=member,
            recommendation=recommendation,
            reasoning=reasoning,
            confidence=0.8,
            key_considerations=[
                "Technical feasibility",
                "Risk assessment",
                "Resource requirements",
            ],
        )

    def get_assistance_stats(self) -> dict:
        """获取辅助统计"""
        return {
            "proposals_analyzed": len(self._proposal_history),
            "avg_complexity": sum(p["analysis"].complexity_score for p in self._proposal_history)
            / max(len(self._proposal_history), 1),
            "avg_risk": sum(p["analysis"].risk_score for p in self._proposal_history)
            / max(len(self._proposal_history), 1),
            "prediction_accuracy": 0.85,  # 模拟
        }
