from __future__ import annotations

"""
---
Type: Organ
Layer: L3
Domain: D-Intelligence
Status: ACTIVE
Version: 1.0.0
Summary: Intelligent recommendation engine for context-aware suggestions
Authority: D-Intelligence/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Recommendation Engine ≡ Engine
# 内涵 ≝ {Recommendation, Engine}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RecommendationEngine)}
# 功能 ⊢ {Recommendation_Engine, Init_Recommendation, Validate_Engine}
# =============================================================================

import logging
from dataclasses import dataclass

from kairon_assistant.command_parser import ParsedCommand
from kairon_assistant.context_manager import ConversationContext
from kairon_assistant.session_manager import AssistantSession
from kairon_assistant.types import CommandType

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """Recommendation item."""

    text: str
    action: str
    confidence: float
    category: str
    reason: str


class RecommendationEngine:
    """Generate intelligent recommendations based on context.

    Features:
    1. Context-aware suggestions
    2. Proactive recommendations
    3. Action-based follow-ups
    4. Usage pattern learning
    """

    def __init__(self) -> None:
        self._command_patterns: dict[str, int] = {}
        self._action_chains: dict[str, list[str]] = self._load_action_chains()

    def get_recommendations(
        self,
        session: AssistantSession,
        conversation: ConversationContext | None,
        last_command: ParsedCommand | None = None,
    ) -> list[Recommendation]:
        """Generate recommendations based on current state."""
        recommendations = []

        # Add command-specific follow-ups
        if last_command:
            recommendations.extend(self._get_follow_up_recommendations(last_command))

        # Add context-based recommendations
        if conversation:
            recommendations.extend(self._get_context_recommendations(conversation))

        # Add proactive system recommendations
        recommendations.extend(self._get_proactive_recommendations())

        # Sort by confidence and return top 5
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations[:5]

    def _get_follow_up_recommendations(self, command: ParsedCommand) -> list[Recommendation]:
        """Get recommendations based on last command."""
        recommendations = []

        # Action-specific follow-ups
        if command.command_type == CommandType.STATUS:
            recommendations.append(
                Recommendation(
                    text="Check specific organ status",
                    action="status D-Execution",
                    confidence=0.85,
                    category="follow_up",
                    reason="You just checked system status",
                )
            )
            recommendations.append(
                Recommendation(
                    text="View dashboard for visual status",
                    action="open dashboard",
                    confidence=0.75,
                    category="follow_up",
                    reason="Visual status might be helpful",
                )
            )

        elif command.command_type == CommandType.ACTION:
            action = command.parameters.get("action", "")
            target = command.parameters.get("target", "")

            if action in ["start", "restart"]:
                recommendations.append(
                    Recommendation(
                        text=f"Check {target} status",
                        action=f"status {target}",
                        confidence=0.9,
                        category="follow_up",
                        reason=f"Verify {target} is running properly",
                    )
                )
                recommendations.append(
                    Recommendation(
                        text=f"Monitor {target} metrics",
                        action=f"metrics {target}",
                        confidence=0.8,
                        category="follow_up",
                        reason="Watch performance after start",
                    )
                )

            elif action == "stop":
                recommendations.append(
                    Recommendation(
                        text=f"Confirm {target} stopped",
                        action=f"status {target}",
                        confidence=0.85,
                        category="follow_up",
                        reason="Verify stop was successful",
                    )
                )

        elif command.command_type == CommandType.QUERY:
            if "organ" in command.parameters or "organ" in command.entities:
                recommendations.append(
                    Recommendation(
                        text="Check organ health",
                        action="health check",
                        confidence=0.8,
                        category="follow_up",
                        reason="After querying organ information",
                    )
                )

        return recommendations

    def _get_context_recommendations(self, conversation: ConversationContext) -> list[Recommendation]:
        """Get recommendations based on conversation context."""
        recommendations = []

        # New user guidance
        if conversation.turn_count <= 2:
            recommendations.append(
                Recommendation(
                    text="See what I can do",
                    action="help",
                    confidence=0.9,
                    category="onboarding",
                    reason="New conversation",
                )
            )
            recommendations.append(
                Recommendation(
                    text="Check system status",
                    action="status",
                    confidence=0.75,
                    category="onboarding",
                    reason="Common first action",
                )
            )

        # Long conversation - suggest starting fresh
        elif conversation.turn_count > 8:
            recommendations.append(
                Recommendation(
                    text="Start a new task",
                    action="clear context",
                    confidence=0.7,
                    category="workflow",
                    reason="Long conversation - might want to start fresh",
                )
            )

        # Check for repeated patterns
        recent_commands = [t.command_type for t in conversation.turns[-3:] if t.command_type]
        if len(recent_commands) >= 2 and recent_commands[-1] == recent_commands[-2]:
            recommendations.append(
                Recommendation(
                    text="Try a different approach",
                    action="suggest alternatives",
                    confidence=0.65,
                    category="workflow",
                    reason="Repeating similar commands",
                )
            )

        return recommendations

    def _get_proactive_recommendations(self) -> list[Recommendation]:
        """Get proactive system recommendations."""
        recommendations = []

        # Common useful actions
        recommendations.append(
            Recommendation(
                text="View system dashboard",
                action="dashboard",
                confidence=0.6,
                category="common",
                reason="Always useful",
            )
        )

        recommendations.append(
            Recommendation(
                text="Check recent alerts", action="alerts", confidence=0.55, category="common", reason="Stay informed"
            )
        )

        recommendations.append(
            Recommendation(
                text="View D-Harvest throughput",
                action="metrics D-Harvest",
                confidence=0.5,
                category="common",
                reason="Key metric",
            )
        )

        return recommendations

    def _load_action_chains(self) -> dict[str, list[str]]:
        """Load common action chains."""
        return {
            "start_organ": ["check_status", "monitor_metrics", "check_logs"],
            "stop_organ": ["confirm_stop", "cleanup"],
            "deploy": ["verify_deployment", "run_tests", "monitor"],
            "config_change": ["validate_config", "apply_change", "verify"],
        }

    def record_command(self, command_type: CommandType, intent: str) -> None:
        """Record command usage for pattern learning."""
        key = f"{command_type.value}:{intent}"
        self._command_patterns[key] = self._command_patterns.get(key, 0) + 1

    def get_popular_commands(self, limit: int = 5) -> list[tuple[str, int]]:
        """Get most popular commands."""
        sorted_commands = sorted(self._command_patterns.items(), key=lambda x: x[1], reverse=True)
        return sorted_commands[:limit]

    def suggest_next_action(self, last_action: str) -> list[Recommendation]:
        """Suggest next actions based on common chains."""
        recommendations = []

        for chain_name, chain_actions in self._action_chains.items():
            if last_action in chain_actions:
                current_idx = chain_actions.index(last_action)
                if current_idx + 1 < len(chain_actions):
                    next_action = chain_actions[current_idx + 1]
                    recommendations.append(
                        Recommendation(
                            text=f"Next: {next_action.replace('_', ' ').title()}",
                            action=next_action,
                            confidence=0.8,
                            category="chain",
                            reason=f"Part of {chain_name} workflow",
                        )
                    )

        return recommendations

    def get_help_suggestions(self, query: str) -> list[Recommendation]:
        """Get contextual help suggestions."""
        suggestions = []

        # Match query to topics
        topics = {
            "organ": [
                Recommendation("List all organs", "list organs", 0.9, "help", "Organ management"),
                Recommendation("Check organ status", "status D-Execution", 0.85, "help", "Organ status"),
                Recommendation("Start/stop organs", "start D-Execution", 0.8, "help", "Organ control"),
            ],
            "dashboard": [
                Recommendation("Open dashboard", "dashboard", 0.9, "help", "Dashboard access"),
                Recommendation("View metrics", "metrics", 0.85, "help", "Dashboard features"),
                Recommendation("Check alerts", "alerts", 0.8, "help", "Dashboard alerts"),
            ],
            "config": [
                Recommendation("View configuration", "config show", 0.9, "help", "Configuration"),
                Recommendation("Update setting", "config set key=value", 0.85, "help", "Configuration"),
            ],
        }

        query_lower = query.lower()
        for keyword, recs in topics.items():
            if keyword in query_lower:
                suggestions.extend(recs)

        if not suggestions:
            # General help
            suggestions = [
                Recommendation("Get system status", "status", 0.8, "help", "General"),
                Recommendation("List available commands", "help commands", 0.75, "help", "General"),
                Recommendation("Show examples", "help examples", 0.7, "help", "General"),
            ]

        return suggestions
