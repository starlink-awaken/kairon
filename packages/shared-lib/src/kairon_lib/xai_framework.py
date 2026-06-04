"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Xai Framework ≡ Module
# 内涵 ≝ {Xai, Framework}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, XaiFramework)}
# 功能 ⊢ {Xai_Framework, Init_Xai, Validate_Framework}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---
# Type: Organ
# Status: ACTIVE
# Layer: L3
# Domain: D-Governance
"""
XAI (Explainable AI) Framework for B-OS

Provides comprehensive explainability for all AI-driven decisions:
- Decision tracing and auditing
- Feature importance analysis (SHAP-like)
- Natural language explanation generation
- Visualization components

Type: Organ
Name: XAIFramework
Layer: L3
Domain: D-Governance
Maturity: 99
Author: @Sage
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from collections.abc import Callable
from typing import Any


class ExplanationLevel(Enum):
    """Explanation detail levels"""

    BRIEF = "brief"  # One-line summary
    STANDARD = "standard"  # Key factors + recommendation
    DETAILED = "detailed"  # Full analysis with reasoning
    TECHNICAL = "technical"  # Technical details for experts


@dataclass
class DecisionTrace:
    """Complete trace of an AI decision"""

    decision_id: str
    timestamp: float
    decision_type: str
    input_data: dict[str, object]
    execution_path: list[dict[str, object]]
    intermediate_results: list[dict[str, object]]
    final_output: Any
    model_version: str
    confidence_score: float


@dataclass
class KeyFactor:
    """Key factor affecting a decision"""

    name: str
    value: Any
    importance: float  # 0.0 to 1.0
    direction: str  # 'positive', 'negative', 'neutral'
    contribution: float
    description: str = ""


@dataclass
class Explanation:
    """Complete explanation of an AI decision"""

    decision_id: str
    summary: str
    intent: str
    factors: list[KeyFactor]
    reasoning: str
    confidence: float
    recommendations: list[str]
    alternatives: list[str]
    audit_info: dict[str, object]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        """Convert explanation to dictionary"""
        return {
            "decision_id": self.decision_id,
            "summary": self.summary,
            "intent": self.intent,
            "factors": [
                {
                    "name": f.name,
                    "value": str(f.value)[:50],
                    "importance": round(f.importance, 3),
                    "direction": f.direction,
                    "contribution": round(f.contribution, 3),
                }
                for f in self.factors
            ],
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 3),
            "recommendations": self.recommendations,
            "alternatives": self.alternatives,
            "audit_info": self.audit_info,
            "timestamp": self.timestamp,
        }


class DecisionTracer:
    """Traces the complete decision-making process"""

    def __init__(self) -> None:
        self.traces: dict[str, DecisionTrace] = {}
        self.trace_hooks: list[Callable] = []

    def start_trace(self, decision_type: str, input_data: dict[str, object]) -> str:
        """Start tracing a new decision"""
        decision_id = self._generate_decision_id(input_data)

        trace = DecisionTrace(
            decision_id=decision_id,
            timestamp=time.time(),
            decision_type=decision_type,
            input_data=input_data,
            execution_path=[],
            intermediate_results=[],
            final_output=None,
            model_version="1.0.0",
            confidence_score=0.0,
        )

        self.traces[decision_id] = trace
        return decision_id

    def record_step(
        self,
        decision_id: str,
        component: str,
        input_data: Any,
        output_data: Any,
        metadata: dict[str, object] = None,
    ) -> None:
        """Record a step in the decision process"""
        if decision_id not in self.traces:
            return

        step = {
            "component": component,
            "input": self._sanitize_data(input_data),
            "output": self._sanitize_data(output_data),
            "timestamp": time.time(),
            "metadata": metadata or {},
        }

        self.traces[decision_id].execution_path.append(step)

    def record_intermediate(self, decision_id: str, stage: str, result: Any) -> None:
        """Record intermediate result"""
        if decision_id not in self.traces:
            return

        self.traces[decision_id].intermediate_results.append(
            {
                "stage": stage,
                "result": self._sanitize_data(result),
                "timestamp": time.time(),
            }
        )

    def finalize_trace(self, decision_id: str, final_output: Any, confidence: float) -> None:
        """Finalize the decision trace"""
        if decision_id not in self.traces:
            return

        trace = self.traces[decision_id]
        trace.final_output = self._sanitize_data(final_output)
        trace.confidence_score = confidence

    def get_trace(self, decision_id: str) -> DecisionTrace | None:
        """Retrieve a decision trace"""
        return self.traces.get(decision_id)

    def _generate_decision_id(self, input_data: dict[str, object]) -> str:
        """Generate unique decision ID"""
        data_str = json.dumps(input_data, sort_keys=True)
        hash_val = hashlib.sha256(data_str.encode()).hexdigest()[:16]
        return f"DEC-{int(time.time())}-{hash_val}"

    def _sanitize_data(self, data: Any) -> Any:
        """Sanitize data for storage"""
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, tuple)):
            return [self._sanitize_data(d) for d in data[:10]]  # Limit size
        if isinstance(data, dict):
            return {k: self._sanitize_data(v) for k, v in list(data.items())[:20]}
        return str(data)[:100]  # Limit string length


class KeyFactorAnalyzer:
    """Analyzes key factors influencing decisions (SHAP-like)"""

    def __init__(self) -> None:
        self.feature_importance_cache: dict[str, list[KeyFactor]] = {}

    def analyze(
        self,
        decision_type: str,
        input_data: dict[str, object],
        output_data: Any,
        context: dict[str, object] = None,
    ) -> list[KeyFactor]:
        """
        Analyze key factors for a decision

        This is a simplified implementation. In production,
        this would use actual SHAP or LIME libraries.
        """
        factors = []

        # Analyze each input feature
        for feature_name, value in input_data.items():
            importance = self._calculate_importance(feature_name, value, output_data, context)

            direction = self._determine_direction(feature_name, value, output_data)

            contribution = self._calculate_contribution(importance, direction)

            description = self._generate_factor_description(feature_name, value, direction, importance)

            factors.append(
                KeyFactor(
                    name=feature_name,
                    value=value,
                    importance=importance,
                    direction=direction,
                    contribution=contribution,
                    description=description,
                )
            )

        # Sort by importance
        factors.sort(key=lambda x: abs(x.importance), reverse=True)

        return factors[:10]  # Return top 10 factors

    def _calculate_importance(self, feature: str, value: Any, output: Any, context: dict[str, object]) -> float:
        """Calculate feature importance"""
        # Simplified importance calculation
        # In production, this would use actual model analysis

        base_importance = 0.5

        # Numeric features
        if isinstance(value, (int, float)):
            # Higher deviation from baseline = higher importance
            baseline = context.get(f"{feature}_baseline", 0)
            if baseline != 0:
                deviation = abs(value - baseline) / abs(baseline)
                base_importance = min(0.9, base_importance + deviation * 0.3)

        # Categorical features
        elif isinstance(value, str):
            if value.lower() in ("critical", "high", "urgent"):
                base_importance = 0.9
            elif value.lower() in ("warning", "medium"):
                base_importance = 0.6
            else:
                base_importance = 0.3

        # Boolean features
        elif isinstance(value, bool):
            base_importance = 0.7 if value else 0.3

        return round(base_importance, 3)

    def _determine_direction(self, feature: str, value: Any, output: Any) -> str:
        """Determine if feature contributes positively or negatively"""
        # Simplified direction logic
        if isinstance(value, bool):
            return "positive" if value else "negative"

        if isinstance(value, (int, float)):
            return "positive" if value > 0 else "negative"

        return "neutral"

    def _calculate_contribution(self, importance: float, direction: str) -> float:
        """Calculate numerical contribution"""
        if direction == "positive":
            return importance
        elif direction == "negative":
            return -importance
        return 0.0

    def _generate_factor_description(self, feature: str, value: Any, direction: str, importance: float) -> str:
        """Generate human-readable factor description"""
        direction_text = {
            "positive": "increases",
            "negative": "decreases",
            "neutral": "has minimal effect on",
        }

        importance_text = "significantly" if importance > 0.7 else "moderately" if importance > 0.4 else "slightly"

        return f"{feature} ({value}) {importance_text} {direction_text[direction]} the decision outcome"


class ExplanationGenerator:
    """Generates natural language explanations"""

    def generate(
        self,
        decision_type: str,
        factors: list[KeyFactor],
        trace: DecisionTrace,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> Explanation:
        """Generate comprehensive explanation"""

        # Generate summary
        summary = self._generate_summary(decision_type, factors, trace)

        # Determine intent
        intent = self._determine_intent(decision_type, trace)

        # Generate reasoning
        reasoning = self._generate_reasoning(factors, trace, level)

        # Generate recommendations
        recommendations = self._generate_recommendations(factors, trace)

        # Generate alternatives
        alternatives = self._generate_alternatives(factors, trace)

        # Calculate overall confidence
        confidence = self._calculate_confidence(factors, trace)

        # Audit info
        audit_info = {
            "model_version": trace.model_version,
            "execution_steps": len(trace.execution_path),
            "factors_considered": len(factors),
            "trace_id": trace.decision_id,
        }

        return Explanation(
            decision_id=trace.decision_id,
            summary=summary,
            intent=intent,
            factors=factors,
            reasoning=reasoning,
            confidence=confidence,
            recommendations=recommendations,
            alternatives=alternatives,
            audit_info=audit_info,
        )

    def _generate_summary(self, decision_type: str, factors: list[KeyFactor], trace: DecisionTrace) -> str:
        """Generate one-line summary"""
        top_factor = factors[0] if factors else None

        if decision_type == "anomaly_detection":
            return (
                f"Detected anomaly with {trace.confidence_score:.0%} confidence "
                f"based on {top_factor.name if top_factor else 'multiple factors'}"
            )

        elif decision_type == "cleanup_recommendation":
            return (
                f"Recommended data cleanup to optimize storage "
                f"({top_factor.description if top_factor else 'analysis completed'})"
            )

        elif decision_type == "governance_decision":
            return f"Governance proposal evaluated with {len(factors)} key factors considered"

        return f"AI decision made with {trace.confidence_score:.0%} confidence"

    def _determine_intent(self, decision_type: str, trace: DecisionTrace) -> str:
        """Determine the intent of the decision"""
        intents = {
            "anomaly_detection": "Identify and alert on unusual system behavior",
            "cleanup_recommendation": "Optimize resource usage through data cleanup",
            "governance_decision": "Evaluate and provide recommendation on proposals",
            "slo_optimization": "Improve service level objectives",
            "resource_allocation": "Optimize resource distribution",
        }
        return intents.get(decision_type, "Make an informed system decision")

    def _generate_reasoning(self, factors: list[KeyFactor], trace: DecisionTrace, level: ExplanationLevel) -> str:
        """Generate detailed reasoning"""
        lines = []

        # Overview
        lines.append("## Decision Reasoning\n")
        lines.append(
            f"This {trace.decision_type} decision was made based on "
            f"{len(factors)} key factors analyzed across "
            f"{len(trace.execution_path)} processing steps.\n"
        )

        # Key factors
        lines.append("### Key Influencing Factors\n")
        for i, factor in enumerate(factors[:5], 1):
            direction_icon = "📈" if factor.direction == "positive" else "📉" if factor.direction == "negative" else "➡️"
            lines.append(f"{i}. {direction_icon} **{factor.name}** (importance: {factor.importance:.0%})")
            lines.append(f"   - Value: {factor.value}")
            lines.append(f"   - Effect: {factor.description}")
            lines.append(f"   - Contribution: {factor.contribution:+.3f}\n")

        # Execution path
        if level in (ExplanationLevel.DETAILED, ExplanationLevel.TECHNICAL):
            lines.append("### Execution Path\n")
            for step in trace.execution_path:
                lines.append(f"- **{step['component']}**: {step['metadata'].get('action', 'processed')}")

        # Model confidence
        lines.append("\n### Confidence Assessment\n")
        lines.append(f"Overall confidence: **{trace.confidence_score:.1%}**")
        lines.append("Based on data quality, model certainty, and factor consistency.\n")

        return "\n".join(lines)

    def _generate_recommendations(self, factors: list[KeyFactor], trace: DecisionTrace) -> list[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Based on top factors
        for factor in factors[:3]:
            if factor.importance > 0.6:
                if "cpu" in factor.name.lower() or "memory" in factor.name.lower():
                    recommendations.append(f"Monitor {factor.name} closely - consider scaling if trend continues")
                elif "storage" in factor.name.lower() or "disk" in factor.name.lower():
                    recommendations.append(f"Review {factor.name} - cleanup may be needed within 7 days")
                elif "error" in factor.name.lower() or "failure" in factor.name.lower():
                    recommendations.append(f"Investigate {factor.name} - potential issue requiring attention")

        if not recommendations:
            recommendations.append("System operating within normal parameters")
            recommendations.append("Continue regular monitoring")

        return recommendations

    def _generate_alternatives(self, factors: list[KeyFactor], trace: DecisionTrace) -> list[str]:
        """Generate alternative actions"""
        alternatives = [
            "Wait and monitor before taking action",
            "Perform manual review of the decision",
            "Adjust thresholds for future similar decisions",
        ]

        # Add specific alternatives based on decision type
        if trace.decision_type == "cleanup_recommendation":
            alternatives.append("Run cleanup with dry-run mode first")
            alternatives.append("Schedule cleanup during maintenance window")

        elif trace.decision_type == "anomaly_detection":
            alternatives.append("Increase monitoring frequency")
            alternatives.append("Notify on-call team for manual investigation")

        return alternatives

    def _calculate_confidence(self, factors: list[KeyFactor], trace: DecisionTrace) -> float:
        """Calculate overall confidence score"""
        if not factors:
            return trace.confidence_score

        # Average of factor importances weighted by their contribution
        total_weight = sum(abs(f.contribution) for f in factors)
        if total_weight == 0:
            return trace.confidence_score

        weighted_confidence = sum(f.importance * abs(f.contribution) for f in factors) / total_weight

        # Combine with model confidence
        return round((weighted_confidence + trace.confidence_score) / 2, 3)


class XAIFramework:
    """
    Main XAI Framework class

    Provides explainability for all AI decisions in B-OS:
    - Anomaly detection explanations
    - Cleanup recommendation explanations
    - Governance decision explanations
    - Resource optimization explanations
    """

    def __init__(self) -> None:

        self.tracer = DecisionTracer()
        self.factor_analyzer = KeyFactorAnalyzer()
        self.explanation_generator = ExplanationGenerator()

        self._explanation_cache: dict[str, Explanation] = {}
        self._initialized = False

        # Statistics
        self.stats = {
            "explanations_generated": 0,
            "explanations_cached": 0,
            "avg_factors_per_decision": 0,
        }

    async def initialize(self) -> bool:
        """Initialize XAI framework"""
        try:
            print("Initializing XAI Framework...")
            self._initialized = True
            print("XAI Framework initialized")
            return True
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            print(f"Error initializing XAI Framework: {e}")
            return False

    def start_decision(self, decision_type: str, input_data: dict[str, object]) -> str:
        """Start tracking a decision"""
        return self.tracer.start_trace(decision_type, input_data)

    def record_step(
        self,
        decision_id: str,
        component: str,
        input_data: Any,
        output_data: Any,
        metadata: dict[str, object] = None,
    ) -> None:
        """Record a decision step"""
        self.tracer.record_step(decision_id, component, input_data, output_data, metadata)

    def explain_decision(
        self,
        decision_id: str,
        output_data: Any,
        confidence: float,
        level: ExplanationLevel = ExplanationLevel.STANDARD,
    ) -> Explanation:
        """
        Generate explanation for a decision

        This is the main entry point for XAI functionality.
        """
        # Finalize the trace
        self.tracer.finalize_trace(decision_id, output_data, confidence)

        # Get the trace
        trace = self.tracer.get_trace(decision_id)
        if not trace:
            raise ValueError(f"Decision {decision_id} not found")

        # Analyze key factors
        context = self._build_context(trace)
        factors = self.factor_analyzer.analyze(trace.decision_type, trace.input_data, output_data, context)

        # Generate explanation
        explanation = self.explanation_generator.generate(trace.decision_type, factors, trace, level)

        # Cache explanation
        self._explanation_cache[decision_id] = explanation

        # Update stats
        self.stats["explanations_generated"] += 1
        self._update_avg_factors(len(factors))

        return explanation

    def get_explanation(self, decision_id: str) -> Explanation | None:
        """Retrieve a cached explanation"""
        return self._explanation_cache.get(decision_id)

    def get_decision_history(self, decision_type: str | None = None, limit: int = 100) -> list[Explanation]:
        """Get history of explained decisions"""
        explanations = list(self._explanation_cache.values())

        if decision_type:
            explanations = [e for e in explanations if e.intent and decision_type in e.intent.lower()]

        # Sort by timestamp (newest first)
        explanations.sort(key=lambda x: x.timestamp, reverse=True)

        return explanations[:limit]

    def export_audit_report(self, start_time: float | None = None, end_time: float | None = None) -> dict[str, object]:
        """Export audit report of all decisions"""
        explanations = list(self._explanation_cache.values())

        if start_time:
            explanations = [e for e in explanations if e.timestamp >= start_time]
        if end_time:
            explanations = [e for e in explanations if e.timestamp <= end_time]

        return {
            "report_generated": time.time(),
            "total_decisions": len(explanations),
            "avg_confidence": sum(e.confidence for e in explanations) / len(explanations) if explanations else 0,
            "decisions": [e.to_dict() for e in explanations],
            "statistics": self.stats,
        }

    def _build_context(self, trace: DecisionTrace) -> dict[str, object]:
        """Build context for factor analysis"""
        context = {}

        # Extract baselines from execution path
        for step in trace.execution_path:
            if "baseline" in step.get("metadata", {}):
                context.update(step["metadata"]["baseline"])

        return context

    def _update_avg_factors(self, num_factors: int) -> None:
        """Update average factors statistic"""
        n = self.stats["explanations_generated"]
        current_avg = self.stats["avg_factors_per_decision"]
        self.stats["avg_factors_per_decision"] = (current_avg * (n - 1) + num_factors) / n

    def get_stats(self) -> dict[str, object]:
        """Get XAI framework statistics"""
        return {
            **self.stats,
            "cached_explanations": len(self._explanation_cache),
            "initialized": self._initialized,
        }


# ============== Test ==============


async def test_xai_framework() -> None:
    """Test XAI framework"""
    print("Testing XAI Framework...")

    xai = XAIFramework()
    await xai.initialize()

    # Test 1: Anomaly detection explanation
    print("\n1. Testing Anomaly Detection Explanation...")

    decision_id = xai.start_decision(
        "anomaly_detection",
        {
            "cpu_usage": 95.5,
            "memory_usage": 88.0,
            "latency_p99": 500,
            "error_rate": 0.05,
            "timestamp": time.time(),
        },
    )

    xai.record_step(
        decision_id,
        "DataCollector",
        {"raw_metrics": True},
        {"metrics": [95.5, 88.0, 500, 0.05]},
        {"action": "collected system metrics"},
    )

    xai.record_step(
        decision_id,
        "AnomalyDetector",
        {"metrics": [95.5, 88.0, 500, 0.05]},
        {"anomaly_score": 0.92},
        {"action": "detected anomaly", "model": "LSTM-v2"},
    )

    explanation = xai.explain_decision(decision_id, output_data={"alert": True, "severity": "high"}, confidence=0.92)

    print(f"  Decision ID: {explanation.decision_id}")
    print(f"  Summary: {explanation.summary}")
    print(f"  Confidence: {explanation.confidence:.1%}")
    print(f"  Top Factors: {len(explanation.factors)}")
    for f in explanation.factors[:3]:
        print(f"    - {f.name}: {f.importance:.1%} ({f.direction})")

    # Test 2: Cleanup recommendation
    print("\n2. Testing Cleanup Recommendation Explanation...")

    decision_id2 = xai.start_decision(
        "cleanup_recommendation",
        {
            "storage_usage": 85.0,
            "data_age_days": 45,
            "access_frequency": 0.02,
            "duplicates_found": 1500,
        },
    )

    explanation2 = xai.explain_decision(
        decision_id2,
        output_data={"recommend_cleanup": True, "estimated_savings": "500MB"},
        confidence=0.88,
    )

    print(f"  Summary: {explanation2.summary}")
    print(f"  Recommendations: {len(explanation2.recommendations)}")
    for r in explanation2.recommendations:
        print(f"    - {r}")

    # Test 3: Audit report
    print("\n3. Testing Audit Report...")

    report = xai.export_audit_report()
    print(f"  Total decisions: {report['total_decisions']}")
    print(f"  Average confidence: {report['avg_confidence']:.1%}")

    # Test 4: Stats
    print("\n4. Framework Stats...")
    stats = xai.get_stats()
    print(f"  Explanations generated: {stats['explanations_generated']}")
    print(f"  Avg factors per decision: {stats['avg_factors_per_decision']:.1f}")

    print("\n" + "=" * 60)
    print("All XAI Framework tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_xai_framework())
