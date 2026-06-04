from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""邮件优先级学习系统 - 通过贝叶斯学习提升分类准确率。

---
Type: Organ
Layer: L3
Domain: D-Memory
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Keywords: [priority, learning, bayesian, email, classification, reputation, feedback]
---

# PriorityLearner ≡ Organ
# 内涵 ≝ {sender_reputation, priority_rules, user_feedback, bayesian_model}
# 外延 ⊢ {e | e ∈ Email ∧ priority_classified(e)}
# 功能 ⊢ {CollectFeedback, UpdateBayesianModel, CalculateReputation, ClassifyPriority}
# =============================================================================

通过贝叶斯学习和用户反馈提升邮件分类准确率。
目标：从 94% 提升至 96%+

Usage::

    learner = PriorityLearner()
    # 收集用户反馈
    learner.collect_feedback(email_id="msg_001", predicted="high", actual="low")
    # 更新贝叶斯模型
    learner.update_bayesian_model(feature_vector, observed_priority)
    # 计算发件人信誉
    score = learner.calculate_sender_reputation(sender="alice@example.com")
    # 分类邮件
    priority = learner.classify_priority(email_features)
"""

import json
import math
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Priority Level Enum
# ---------------------------------------------------------------------------


class PriorityLevel(StrEnum):
    """邮件优先级等级。"""

    CRITICAL = "critical"  # 紧急/重要
    HIGH = "high"  # 高优先级
    NORMAL = "normal"  # 普通
    LOW = "low"  # 低优先级
    SPAM = "spam"  # 垃圾邮件


# ---------------------------------------------------------------------------
# 数据类定义
# ---------------------------------------------------------------------------


@dataclass
class SenderReputation:
    """发件人信誉评分。"""

    email: str
    total_emails: int = 0
    correct_classifications: int = 0
    user_corrections: int = 0  # 用户修正次数
    reputation_score: float = 0.5  # 0.0 - 1.0
    last_email_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    domain_reputation: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "total_emails": self.total_emails,
            "correct_classifications": self.correct_classifications,
            "user_corrections": self.user_corrections,
            "reputation_score": round(self.reputation_score, 4),
            "last_email_at": self.last_email_at.isoformat(),
            "domain_reputation": round(self.domain_reputation, 4),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SenderReputation:
        return cls(
            email=d["email"],
            total_emails=d.get("total_emails", 0),
            correct_classifications=d.get("correct_classifications", 0),
            user_corrections=d.get("user_corrections", 0),
            reputation_score=d.get("reputation_score", 0.5),
            last_email_at=_parse_dt(d.get("last_email_at")),
            domain_reputation=d.get("domain_reputation", 0.5),
            created_at=_parse_dt(d.get("created_at")),
        )


@dataclass
class UserFeedback:
    """用户反馈记录。"""

    email_id: str
    sender: str
    predicted_priority: PriorityLevel
    actual_priority: PriorityLevel
    feedback_type: str  # 'confirm' | 'correction'
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    features_hash: str = ""  # 邮件特征哈希，用于关联学习

    def to_dict(self) -> dict[str, Any]:
        return {
            "email_id": self.email_id,
            "sender": self.sender,
            "predicted_priority": self.predicted_priority.value,
            "actual_priority": self.actual_priority.value,
            "feedback_type": self.feedback_type,
            "timestamp": self.timestamp.isoformat(),
            "features_hash": self.features_hash,
        }


@dataclass
class BayesianPrior:
    """贝叶斯先验分布参数。"""

    feature_name: str
    priority_level: PriorityLevel
    alpha: float = 1.0  # Beta分布α参数（成功次数+1）
    beta: float = 1.0  # Beta分布β参数（失败次数+1）
    total_observations: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "priority_level": self.priority_level.value,
            "alpha": self.alpha,
            "beta": self.beta,
            "total_observations": self.total_observations,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BayesianPrior:
        return cls(
            feature_name=d["feature_name"],
            priority_level=PriorityLevel(d["priority_level"]),
            alpha=d.get("alpha", 1.0),
            beta=d.get("beta", 1.0),
            total_observations=d.get("total_observations", 0),
            updated_at=_parse_dt(d.get("updated_at")),
        )

    def get_posterior_mean(self) -> float:
        """计算后验分布的均值（期望概率）。"""
        return self.alpha / (self.alpha + self.beta)

    def get_confidence_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """计算置信区间（使用正态近似）。"""
        mean = self.get_posterior_mean()
        variance = (self.alpha * self.beta) / ((self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1))
        std = math.sqrt(variance)
        # 95% CI ≈ mean ± 1.96 * std
        z = 1.96 if confidence == 0.95 else 2.576  # 99% CI
        margin = z * std
        return (max(0.0, mean - margin), min(1.0, mean + margin))


@dataclass
class EmailFeatures:
    """邮件特征向量。"""

    sender: str
    subject_keywords: list[str] = field(default_factory=list)
    has_attachment: bool = False
    time_of_day: str = "morning"  # morning | afternoon | evening | night
    is_internal: bool = False  # 是否内部邮件
    recipient_count: int = 1
    thread_depth: int = 0  # 邮件链深度
    sender_domain: str = ""

    def to_feature_vector(self) -> dict[str, Any]:
        """转换为特征字典。"""
        return {
            "sender": self.sender,
            "subject_keyword_count": len(self.subject_keywords),
            "has_attachment": self.has_attachment,
            "time_of_day": self.time_of_day,
            "is_internal": self.is_internal,
            "recipient_count": self.recipient_count,
            "thread_depth": self.thread_depth,
            "sender_domain": self.sender_domain or self.sender.split("@")[-1] if "@" in self.sender else "unknown",
        }

    def get_feature_hash(self) -> str:
        """生成特征哈希用于关联学习。"""
        import hashlib

        feature_str = json.dumps(self.to_feature_vector(), sort_keys=True)
        return hashlib.md5(feature_str.encode()).hexdigest()[:16]  # noqa: S324


def _parse_dt(value: Any) -> datetime:
    """解析日期时间。"""
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# PriorityLearner 主类
# ---------------------------------------------------------------------------


class PriorityLearner:
    """邮件优先级学习系统。

    核心功能：
    1. 用户反馈收集 - 记录用户确认和修正
    2. 贝叶斯学习 - 更新优先级分类规则
    3. 发件人信誉评分 - 动态评估发件人可信度

    BOS-URI endpoints
    -----------------
    ``bos://memory/priority/feedback``      — 提交用户反馈
    ``bos://memory/priority/classify``      — 分类邮件优先级
    ``bos://memory/priority/reputation``    — 查询发件人信誉
    ``bos://memory/priority/stats``         — 获取学习统计
    """

    # 学习参数
    CONFIDENCE_THRESHOLD = 0.85  # 置信度阈值
    REPUTATION_DECAY_DAYS = 30  # 信誉衰减天数
    MIN_FEEDBACK_FOR_UPDATE = 5  # 最小反馈数触发更新
    BAYESIAN_LEARNING_RATE = 0.1  # 贝叶斯学习率

    # 关键词库
    CRITICAL_KEYWORDS = ["urgent", "asap", "deadline", "critical", "重要", "紧急", "immediately"]
    HIGH_KEYWORDS = ["action required", "response needed", "please review", "attention"]
    SPAM_KEYWORDS = ["unsubscribe", "promotion", "广告", "优惠", "discount", "limited time", "click here"]

    def __init__(
        self,
        metadata_path: str = "organs/D-Memory/organs/growth/priority_learner.py",
    ) -> None:
        self._lock = threading.RLock()
        self.status = "ACTIVE"

        # 发件人信誉存储: email -> SenderReputation
        self._sender_reputation: dict[str, SenderReputation] = {}

        # 用户反馈历史
        self._feedback_history: list[UserFeedback] = []

        # 贝叶斯先验存储: (feature_name, priority_level) -> BayesianPrior
        self._bayesian_priors: dict[tuple[str, PriorityLevel], BayesianPrior] = {}

        # 分类准确率统计
        self._classification_stats: dict[str, Any] = {
            "total": 0,
            "correct": 0,
            "by_priority": {p.value: {"total": 0, "correct": 0} for p in PriorityLevel},
        }

        # 启发式规则权重（将被贝叶斯更新调整）
        self._rule_weights = {
            "sender_reputation": 0.25,
            "keyword_match": 0.35,
            "time_sensitivity": 0.10,
            "thread_importance": 0.10,
            "recipient_scope": 0.05,
            "attachment_relevance": 0.10,
            "internal_flag": 0.05,
        }

        _log.info("PriorityLearner initialized")

    # -------------------------------------------------------------------------
    # 1. 用户反馈收集
    # -------------------------------------------------------------------------

    def collect_feedback(
        self,
        email_id: str,
        sender: str,
        predicted: PriorityLevel | str,
        actual: PriorityLevel | str,
        features: EmailFeatures | None = None,
    ) -> UserFeedback:
        """收集用户对优先级分类的反馈。

        Args:
            email_id: 邮件唯一标识
            sender: 发件人邮箱
            predicted: 系统预测的优先级
            actual: 用户确认的优先级
            features: 邮件特征（可选，用于关联学习）

        Returns:
            UserFeedback: 反馈记录
        """
        pred = PriorityLevel(predicted) if isinstance(predicted, str) else predicted
        act = PriorityLevel(actual) if isinstance(actual, str) else actual

        feedback_type = "confirm" if pred == act else "correction"

        feedback = UserFeedback(
            email_id=email_id,
            sender=sender,
            predicted_priority=pred,
            actual_priority=act,
            feedback_type=feedback_type,
            features_hash=features.get_feature_hash() if features else "",
        )

        with self._lock:
            self._feedback_history.append(feedback)

            # 更新分类统计
            self._classification_stats["total"] += 1
            if pred == act:
                self._classification_stats["correct"] += 1
            self._classification_stats["by_priority"][act.value]["total"] += 1
            if pred == act:
                self._classification_stats["by_priority"][act.value]["correct"] += 1

            # 更新发件人信誉
            self._update_sender_reputation(sender, pred == act)

            # 如果有足够反馈，触发贝叶斯更新
            if len(self._feedback_history) >= self.MIN_FEEDBACK_FOR_UPDATE:
                self._trigger_bayesian_update(features, act)

        _log.info(
            "[PriorityLearner] Feedback collected: %s -> %s (type=%s, sender=%s)",
            pred.value,
            act.value,
            feedback_type,
            sender,
        )
        return feedback

    # -------------------------------------------------------------------------
    # 2. 贝叶斯学习更新
    # -------------------------------------------------------------------------

    def update_bayesian_model(
        self,
        feature_name: str,
        feature_value: bool,
        observed_priority: PriorityLevel,
    ) -> BayesianPrior:
        """使用贝叶斯更新规则更新先验分布。

        使用 Beta 分布作为共轭先验：
        - P(θ|data) ∝ P(data|θ) * P(θ)
        - Beta(α, β) 更新: 观测到"成功"时 α+1，"失败"时 β+1

        Args:
            feature_name: 特征名称
            feature_value: 特征值是否支持该优先级
            observed_priority: 观察到的优先级

        Returns:
            BayesianPrior: 更新后的先验
        """
        key = (feature_name, observed_priority)

        with self._lock:
            prior = self._bayesian_priors.get(key)
            if prior is None:
                prior = BayesianPrior(
                    feature_name=feature_name,
                    priority_level=observed_priority,
                )
                self._bayesian_priors[key] = prior

            # Beta 分布更新
            if feature_value:
                # 特征支持该优先级
                prior.alpha += 1.0
            else:
                # 特征不支持该优先级
                prior.beta += 1.0

            prior.total_observations += 1
            prior.updated_at = datetime.now(UTC)

        _log.debug(
            "[PriorityLearner] Bayesian update: %s|%s α=%.2f β=%.2f",
            feature_name,
            observed_priority.value,
            prior.alpha,
            prior.beta,
        )
        return prior

    def _trigger_bayesian_update(
        self,
        features: EmailFeatures | None,
        actual_priority: PriorityLevel,
    ) -> None:
        """触发贝叶斯模型更新（内部方法）。"""
        if features is None:
            return

        fv = features.to_feature_vector()

        # 更新各特征的贝叶斯先验
        # 1. 附件特征
        self.update_bayesian_model("has_attachment", fv["has_attachment"], actual_priority)

        # 2. 内部邮件特征
        self.update_bayesian_model("is_internal", fv["is_internal"], actual_priority)

        # 3. 时间特征
        time_features = {
            "morning": actual_priority in (PriorityLevel.CRITICAL, PriorityLevel.HIGH),
            "afternoon": actual_priority == PriorityLevel.NORMAL,
            "evening": actual_priority == PriorityLevel.LOW,
            "night": actual_priority == PriorityLevel.SPAM,
        }
        for time_val, is_match in time_features.items():
            self.update_bayesian_model(f"time_{time_val}", is_match, actual_priority)

        # 4. 收件人数量特征
        multi_recipient = fv["recipient_count"] > 1
        self.update_bayesian_model("multi_recipient", multi_recipient, actual_priority)

        # 5. 邮件链深度
        thread_active = fv["thread_depth"] > 0
        self.update_bayesian_model("thread_active", thread_active, actual_priority)

    def get_bayesian_probability(
        self,
        feature_name: str,
        priority_level: PriorityLevel,
    ) -> float:
        """获取特征对优先级的贝叶斯后验概率。

        Args:
            feature_name: 特征名称
            priority_level: 优先级等级

        Returns:
            float: 后验概率 P(priority|feature)
        """
        key = (feature_name, priority_level)
        with self._lock:
            prior = self._bayesian_priors.get(key)
            if prior is None:
                return 0.5  # 无先验时返回中性值
            return prior.get_posterior_mean()

    # -------------------------------------------------------------------------
    # 3. 发件人信誉评分系统
    # -------------------------------------------------------------------------

    def calculate_sender_reputation(self, sender: str) -> SenderReputation:
        """计算或获取发件人信誉评分。

        信誉评分算法：
        - 基础分：0.5
        - 正确分类奖励：+0.1/次
        - 用户修正惩罚：-0.15/次
        - 时间衰减：30天内无邮件 -10%

        Args:
            sender: 发件人邮箱

        Returns:
            SenderReputation: 发件人信誉对象
        """
        with self._lock:
            reputation = self._sender_reputation.get(sender)

            if reputation is None:
                # 新建发件人记录
                domain = sender.split("@")[-1] if "@" in sender else "unknown"
                reputation = SenderReputation(
                    email=sender,
                    domain_reputation=self._estimate_domain_reputation(domain),
                )
                self._sender_reputation[sender] = reputation

            # 应用时间衰减
            self._apply_reputation_decay(reputation)

            return reputation

    def _update_sender_reputation(self, sender: str, was_correct: bool) -> None:
        """更新发件人信誉（内部方法）。"""
        reputation = self.calculate_sender_reputation(sender)

        reputation.total_emails += 1
        reputation.last_email_at = datetime.now(UTC)

        if was_correct:
            reputation.correct_classifications += 1
            # 正确分类奖励
            reputation.reputation_score = min(1.0, reputation.reputation_score + 0.05)
        else:
            reputation.user_corrections += 1
            # 用户修正惩罚
            reputation.reputation_score = max(0.0, reputation.reputation_score - 0.08)

        # 综合评分：考虑历史准确率和近期表现
        if reputation.total_emails > 0:
            accuracy = reputation.correct_classifications / reputation.total_emails
            # 加权平均：历史权重 0.6，当前评分 0.4
            reputation.reputation_score = 0.6 * accuracy + 0.4 * reputation.reputation_score

    def _apply_reputation_decay(self, reputation: SenderReputation) -> None:
        """应用信誉时间衰减。"""
        days_since_last = (datetime.now(UTC) - reputation.last_email_at).total_seconds() / 86400

        if days_since_last > self.REPUTATION_DECAY_DAYS:
            # 超过30天未联系，信誉轻微衰减
            decay_factor = math.exp(-0.01 * (days_since_last - self.REPUTATION_DECAY_DAYS))
            reputation.reputation_score *= max(0.8, decay_factor)

    def _estimate_domain_reputation(self, domain: str) -> float:
        """估算域名信誉（基于历史数据）。"""
        # 收集该域名下所有发件人的平均信誉
        domain_scores = [r.reputation_score for r in self._sender_reputation.values() if r.email.endswith(f"@{domain}")]

        if not domain_scores:
            return 0.5  # 未知域名中性值

        return sum(domain_scores) / len(domain_scores)

    # -------------------------------------------------------------------------
    # 4. 邮件分类
    # -------------------------------------------------------------------------

    def classify_priority(
        self,
        features: EmailFeatures,
        use_bayesian: bool = True,
    ) -> tuple[PriorityLevel, float]:
        """分类邮件优先级。

        使用贝叶斯后验概率和启发式规则的组合评分。

        Args:
            features: 邮件特征
            use_bayesian: 是否使用贝叶斯概率

        Returns:
            tuple[PriorityLevel, float]: (优先级, 置信度)
        """
        fv = features.to_feature_vector()
        scores: dict[PriorityLevel, float] = dict.fromkeys(PriorityLevel, 0.0)

        # 基础分确保每种优先级都有基础概率
        base_scores = {
            PriorityLevel.CRITICAL: 0.05,
            PriorityLevel.HIGH: 0.15,
            PriorityLevel.NORMAL: 0.40,
            PriorityLevel.LOW: 0.25,
            PriorityLevel.SPAM: 0.15,
        }
        for p, s in base_scores.items():
            scores[p] += s

        # 1. 发件人信誉评分
        sender_rep = self.calculate_sender_reputation(features.sender)
        sender_weight = self._rule_weights["sender_reputation"]

        # 高信誉发件人倾向于高优先级
        if sender_rep.reputation_score >= 0.7:
            scores[PriorityLevel.HIGH] += sender_weight * 1.5
            scores[PriorityLevel.CRITICAL] += sender_weight * 0.8
            scores[PriorityLevel.SPAM] -= sender_weight * 0.5
        elif sender_rep.reputation_score >= 0.5:
            scores[PriorityLevel.HIGH] += sender_weight * 0.8
            scores[PriorityLevel.NORMAL] += sender_weight * 0.3
        elif sender_rep.reputation_score < 0.3:
            scores[PriorityLevel.SPAM] += sender_weight * 1.5
            scores[PriorityLevel.LOW] += sender_weight * 0.8
            scores[PriorityLevel.HIGH] -= sender_weight * 0.3

        # 2. 关键词匹配（核心规则）
        keyword_weight = self._rule_weights["keyword_match"]
        subject_lower = " ".join(features.subject_keywords).lower()

        # 关键紧急词
        if any(kw in subject_lower for kw in self.CRITICAL_KEYWORDS):
            scores[PriorityLevel.CRITICAL] += keyword_weight * 2.0
            scores[PriorityLevel.HIGH] += keyword_weight * 0.8
            scores[PriorityLevel.SPAM] -= keyword_weight * 0.5
            scores[PriorityLevel.LOW] -= keyword_weight * 0.3

        # 高优先级词
        if any(kw in subject_lower for kw in self.HIGH_KEYWORDS):
            scores[PriorityLevel.HIGH] += keyword_weight * 1.2
            scores[PriorityLevel.CRITICAL] += keyword_weight * 0.3

        # 垃圾邮件词
        if any(kw in subject_lower for kw in self.SPAM_KEYWORDS):
            scores[PriorityLevel.SPAM] += keyword_weight * 2.0
            scores[PriorityLevel.LOW] += keyword_weight * 0.8
            scores[PriorityLevel.CRITICAL] -= keyword_weight * 0.5
            scores[PriorityLevel.HIGH] -= keyword_weight * 0.3

        # 3. 结构化特征规则
        # 内部+附件+早上 = 高优先级
        if features.is_internal and features.has_attachment and fv["time_of_day"] == "morning":
            scores[PriorityLevel.HIGH] += 0.4
            scores[PriorityLevel.CRITICAL] += 0.2

        # 外部+无附件+晚上 = 低优先级
        if not features.is_internal and not features.has_attachment and fv["time_of_day"] in ("evening", "night"):
            scores[PriorityLevel.LOW] += 0.3
            scores[PriorityLevel.SPAM] += 0.2

        # 4. 贝叶斯特征概率（如果已学习足够数据）
        if use_bayesian and len(self._bayesian_priors) > 10:
            for priority in PriorityLevel:
                # 附件特征
                p_attach = self.get_bayesian_probability("has_attachment", priority)
                if p_attach != 0.5:
                    scores[priority] += self._rule_weights["attachment_relevance"] * (p_attach - 0.5) * 2

                # 内部邮件
                p_internal = self.get_bayesian_probability("is_internal", priority)
                if p_internal != 0.5:
                    scores[priority] += self._rule_weights["internal_flag"] * (p_internal - 0.5) * 2

                # 时间特征
                time_key = f"time_{fv['time_of_day']}"
                p_time = self.get_bayesian_probability(time_key, priority)
                if p_time != 0.5:
                    scores[priority] += self._rule_weights["time_sensitivity"] * (p_time - 0.5) * 2

        # 5. 选择最高分的优先级
        best_priority = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_priority]

        # 6. 计算置信度
        total_score = sum(abs(s) for s in scores.values())
        if total_score > 0:
            confidence = abs(best_score) / total_score
        else:
            confidence = 0.5

        # 确保置信度在合理范围
        confidence = max(0.5, min(1.0, confidence + 0.3))

        return best_priority, round(confidence, 4)

    # -------------------------------------------------------------------------
    # 5. 统计与报告
    # -------------------------------------------------------------------------

    def get_classification_accuracy(self) -> float:
        """获取当前分类准确率。"""
        with self._lock:
            total = self._classification_stats["total"]
            if total == 0:
                return 0.0
            return self._classification_stats["correct"] / total

    def get_stats(self) -> dict[str, Any]:
        """获取学习系统统计信息。"""
        with self._lock:
            total = self._classification_stats["total"]
            correct = self._classification_stats["correct"]

            # 计算各优先级准确率
            by_priority = {}
            for p in PriorityLevel:
                stats = self._classification_stats["by_priority"][p.value]
                p_total = stats["total"]
                by_priority[p.value] = {
                    "total": p_total,
                    "correct": stats["correct"],
                    "accuracy": round(stats["correct"] / p_total, 4) if p_total > 0 else 0.0,
                }

            # 发件人信誉分布
            reputation_dist = {"high": 0, "medium": 0, "low": 0}
            for rep in self._sender_reputation.values():
                if rep.reputation_score >= 0.7:
                    reputation_dist["high"] += 1
                elif rep.reputation_score >= 0.4:
                    reputation_dist["medium"] += 1
                else:
                    reputation_dist["low"] += 1

            return {
                "classification_accuracy": round(correct / total, 4) if total > 0 else 0.0,
                "total_classifications": total,
                "correct_classifications": correct,
                "feedback_count": len(self._feedback_history),
                "correction_count": sum(1 for f in self._feedback_history if f.feedback_type == "correction"),
                "by_priority": by_priority,
                "sender_reputation_dist": reputation_dist,
                "bayesian_priors_count": len(self._bayesian_priors),
                "unique_senders": len(self._sender_reputation),
            }

    def get_learning_report(self) -> dict[str, Any]:
        """生成学习效果报告。"""
        stats = self.get_stats()
        accuracy = stats["classification_accuracy"]

        # 分析改进趋势
        recent_feedback = [
            f for f in self._feedback_history[-50:] if f.timestamp > datetime.now(UTC) - timedelta(days=7)
        ]
        recent_corrections = sum(1 for f in recent_feedback if f.feedback_type == "correction")
        recent_accuracy = (len(recent_feedback) - recent_corrections) / len(recent_feedback) if recent_feedback else 0.0

        return {
            "overall_accuracy": round(accuracy * 100, 2),
            "recent_7d_accuracy": round(recent_accuracy * 100, 2),
            "target_accuracy": 96.0,
            "gap_to_target": round(max(0, 96.0 - accuracy * 100), 2),
            "improvement_suggestions": self._generate_improvement_suggestions(stats),
            "top_trusted_senders": self._get_top_senders(5),
        }

    def _generate_improvement_suggestions(self, stats: dict[str, Any]) -> list[str]:
        """生成改进建议。"""
        suggestions = []
        accuracy = stats["classification_accuracy"]

        if accuracy < 0.96:
            gap = 0.96 - accuracy
            suggestions.append(f"需要收集更多反馈数据来缩小 {gap * 100:.1f}% 的准确率差距")

        correction_rate = stats["correction_count"] / max(1, stats["feedback_count"])
        if correction_rate > 0.1:
            suggestions.append(f"修正率较高 ({correction_rate * 100:.1f}%)，建议调整规则权重")

        if stats["bayesian_priors_count"] < 20:
            suggestions.append("贝叶斯先验数据不足，建议增加训练样本")

        return suggestions

    def _get_top_senders(self, n: int = 5) -> list[dict[str, Any]]:
        """获取高信誉发件人列表。"""
        sorted_senders = sorted(
            self._sender_reputation.values(),
            key=lambda r: r.reputation_score,
            reverse=True,
        )
        return [
            {
                "email": s.email,
                "reputation": round(s.reputation_score, 3),
                "total_emails": s.total_emails,
                "accuracy": round(s.correct_classifications / s.total_emails, 3) if s.total_emails > 0 else 0,
            }
            for s in sorted_senders[:n]
        ]

    # -------------------------------------------------------------------------
    # CoreService 接口实现
    # -------------------------------------------------------------------------

    def validate_access(self, operation: str, context: dict[str, Any]) -> bool:
        return True

    def get_metadata(self) -> dict[str, Any]:
        return {
            "name": "PriorityLearner",
            "domain": "D-Memory",
            "layer": "L3",
            "version": "1.0.0",
            "status": self.status,
        }

    def get_registry_info(self) -> dict[str, Any]:
        return {
            "bos_uri": "bos://memory/priority",
            "endpoints": [
                "bos://memory/priority/feedback",
                "bos://memory/priority/classify",
                "bos://memory/priority/reputation",
                "bos://memory/priority/stats",
            ],
        }
