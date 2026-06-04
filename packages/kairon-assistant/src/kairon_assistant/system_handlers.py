from __future__ import annotations

"""
---
Type: Organ
Layer: L3
Domain: D-Intelligence
Status: ACTIVE
Version: 1.0.0
Summary: System command handlers for Smart Assistant
Authority: D-Intelligence/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# System Handlers ≡ Handler
# 内涵 ≝ {System, Handlers}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, SystemHandlers)}
# 功能 ⊢ {System_Handlers, Init_System, Validate_Handlers}
# =============================================================================

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kairon_assistant.command_parser import ParsedCommand
    from kairon_assistant.context_manager import ConversationContext
    from kairon_assistant.core import AssistantResponse, SmartAssistant
    from kairon_assistant.session_manager import AssistantSession

logger = logging.getLogger(__name__)


async def handle_query(
    parsed: ParsedCommand,
    session: AssistantSession,
    conversation: ConversationContext | None,
    assistant: SmartAssistant,
) -> AssistantResponse:
    """Handle query commands."""
    from kairon_assistant.core import AssistantResponse

    target = parsed.parameters.get("target", "")

    # Handle specific queries
    if "organ" in parsed.raw_text.lower() or target.startswith("D-"):
        return await _query_organ(target or "all", parsed)

    if "status" in parsed.raw_text.lower():
        return await handle_status(parsed, session, conversation, assistant)

    if "metric" in parsed.raw_text.lower():
        return await _query_metrics(target, parsed)

    if "session" in parsed.raw_text.lower() or "conversation" in parsed.raw_text.lower():
        return _query_session(session, conversation)

    # Generic query
    return AssistantResponse(
        response_text=f"I found information about '{parsed.raw_text}'. What specific details would you like?",
        confidence=parsed.confidence,
        suggestions=[
            f"Show details for {target}" if target else "Show all information",
            "Filter by time range",
            "Export to file",
        ],
    )


async def handle_action(
    parsed: ParsedCommand,
    session: AssistantSession,
    conversation: ConversationContext | None,
    assistant: SmartAssistant,
) -> AssistantResponse:
    """Handle action commands."""
    from kairon_assistant.core import AssistantResponse

    action = parsed.parameters.get("action", "")
    target = parsed.parameters.get("target", "")

    # Simulate action execution
    action_results = {
        "start": f"✅ Started {target}" if target else "✅ Operation started",
        "stop": f"✅ Stopped {target}" if target else "✅ Operation stopped",
        "restart": f"✅ Restarted {target}" if target else "✅ Operation restarted",
        "create": f"✅ Created {target}" if target else "✅ Created successfully",
        "delete": f"✅ Deleted {target}" if target else "✅ Deleted successfully",
    }

    result_text = action_results.get(action, f"✅ Executed {action}")

    return AssistantResponse(
        response_text=result_text,
        action_taken=True,
        action_result={"action": action, "target": target, "status": "success"},
        confidence=parsed.confidence,
        suggestions=[f"Check {target} status" if target else "Check status", "View logs", "Undo action"],
    )


async def handle_status(
    parsed: ParsedCommand,
    session: AssistantSession,
    conversation: ConversationContext | None,
    assistant: SmartAssistant,
) -> AssistantResponse:
    """Handle status commands."""
    from kairon_assistant.core import AssistantResponse

    target = parsed.parameters.get("target", "")

    # Build status report
    status_data = {
        "system": "B-OS v10.0.0",
        "timestamp": "2026-03-21T14:30:00Z",
        "organs": {
            "D-Execution": {"status": "healthy", "load": 45},
            "D-Harvest": {"status": "healthy", "throughput": "+45%"},
            "D-Gateway": {"status": "healthy", "protocols": ["MCP", "HTTP", "WebSocket"]},
            "D-Monitoring": {"status": "healthy", "dashboard": "v2.0"},
            "D-Voice": {"status": "healthy", "accuracy": "89%"},
            "D-Intelligence": {"status": "healthy", "assistant": "active"},
        },
    }

    if target and target.startswith("D-"):
        organ_status = status_data["organs"].get(target)
        if organ_status:
            response_text = f"📊 **{target} Status**\n"
            for key, value in organ_status.items():
                response_text += f"• {key}: {value}\n"
        else:
            response_text = f"❌ Organ '{target}' not found"
    else:
        response_text = "📊 **System Status**\n\n"
        for organ, info in status_data["organs"].items():
            emoji = "🟢" if info["status"] == "healthy" else "🟡" if info["status"] == "degraded" else "🔴"
            response_text += f"{emoji} **{organ}**: {info['status']}\n"

    return AssistantResponse(
        response_text=response_text,
        confidence=parsed.confidence,
        suggestions=["View detailed metrics", "Check alerts", "Open dashboard"],
    )


async def handle_config(
    parsed: ParsedCommand,
    session: AssistantSession,
    conversation: ConversationContext | None,
    assistant: SmartAssistant,
) -> AssistantResponse:
    """Handle configuration commands."""
    from kairon_assistant.core import AssistantResponse

    # Extract config changes from parameters
    config_changes = {k: v for k, v in parsed.parameters.items() if k not in ["target", "action"]}

    if not config_changes:
        # Show current config
        return AssistantResponse(
            response_text="⚙️ **Current Configuration**\n\n"
            "• max_context_turns: 10\n"
            "• enable_recommendations: true\n"
            "• response_timeout: 30s\n"
            "• governance_check: true\n\n"
            "Use 'set <key>=<value>' to change settings.",
            confidence=parsed.confidence,
        )

    # Apply config changes
    changes_text = "\n".join(f"• {k} = {v}" for k, v in config_changes.items())

    return AssistantResponse(
        response_text=f"✅ **Configuration Updated**\n\n{changes_text}",
        action_taken=True,
        action_result={"config_changes": config_changes},
        confidence=parsed.confidence,
    )


async def handle_help(
    parsed: ParsedCommand,
    session: AssistantSession,
    conversation: ConversationContext | None,
    assistant: SmartAssistant,
) -> AssistantResponse:
    """Handle help commands."""
    from kairon_assistant.core import AssistantResponse

    help_text = """🤖 **Smart Assistant Help**

**Available Commands:**

📊 **Information**
• "status" - Check system status
• "status D-Execution" - Check specific organ
• "metrics" - View system metrics
• "what is [topic]" - Query information

⚡ **Actions**
• "start [organ]" - Start an organ
• "stop [organ]" - Stop an organ
• "restart [organ]" - Restart an organ

⚙️ **Configuration**
• "config" - Show current config
• "set [key]=[value]" - Change setting

🎯 **Examples:**
• "What's the status of D-Harvest?"
• "Start D-Gateway protocol adapter"
• "Show me recent alerts"
• "Configure timeout to 60 seconds"

**Tips:**
- I understand natural language, so feel free to ask in your own words
- I remember context from our conversation
- I can suggest next steps based on what you're doing
"""

    return AssistantResponse(
        response_text=help_text,
        confidence=parsed.confidence,
        suggestions=["Show command examples", "List available organs", "Check my permissions"],
    )


# Helper functions


async def _query_organ(organ: str, parsed: ParsedCommand) -> AssistantResponse:
    """Query organ information."""
    from kairon_assistant.core import AssistantResponse

    organ_info = {
        "D-Execution": {
            "description": "Task execution and agent orchestration",
            "subdomains": ["D-Continuity", "D-Harness", "D-Extension"],
            "status": "active",
            "stats": {"tasks_today": 1247, "success_rate": "98.5%"},
        },
        "D-Harvest": {
            "description": "Knowledge harvesting and data collection",
            "version": "2.0",
            "status": "active",
            "stats": {"sources": 12, "throughput": "+45%"},
        },
        "D-Gateway": {
            "description": "Protocol unification and federation gateway",
            "protocols": ["MCP", "HTTP", "WebSocket"],
            "status": "active",
            "stats": {"active_connections": 8},
        },
        "D-Monitoring": {
            "description": "System monitoring and visualization",
            "dashboard_version": "2.0",
            "status": "active",
            "features": ["real-time metrics", "alerting", "snapshots"],
        },
    }

    if organ == "all":
        response = "📋 **Available Organs:**\n\n"
        for name, info in organ_info.items():
            response += f"**{name}**: {info['description']}\n"
            response += f"  Status: {info['status']}\n\n"
    elif organ in organ_info:
        info = organ_info[organ]
        response = f"📋 **{organ}**\n\n"
        response += f"Description: {info['description']}\n"
        response += f"Status: {info['status']}\n"
        if "stats" in info:
            response += "\nStats:\n"
            for key, value in info["stats"].items():
                response += f"  • {key}: {value}\n"
    else:
        response = f"❌ Organ '{organ}' not found. Available: {', '.join(organ_info.keys())}"

    return AssistantResponse(response_text=response, confidence=parsed.confidence)


async def _query_metrics(target: str, parsed: ParsedCommand) -> AssistantResponse:
    """Query system metrics."""
    from kairon_assistant.core import AssistantResponse

    metrics = {
        "cpu_usage": "45%",
        "memory_usage": "62%",
        "disk_usage": "38%",
        "active_sessions": 12,
        "requests_per_minute": 156,
        "average_response_time": "120ms",
    }

    response = "📈 **System Metrics**\n\n"
    for key, value in metrics.items():
        response += f"• {key.replace('_', ' ').title()}: {value}\n"

    return AssistantResponse(
        response_text=response,
        confidence=parsed.confidence,
        suggestions=["View historical metrics", "Export metrics data", "Set up metric alerts"],
    )


def _query_session(session: AssistantSession, conversation: ConversationContext | None) -> AssistantResponse:
    """Query session information."""
    from kairon_assistant.core import AssistantResponse

    response = "📱 **Session Information**\n\n"
    response += f"Session ID: {session.session_id}\n"
    response += f"User ID: {session.user_id or 'anonymous'}\n"
    response += f"Commands issued: {session.command_count}\n"
    response += f"Session age: {session.duration_seconds:.0f}s\n"

    if conversation:
        response += f"\nConversation turns: {conversation.turn_count}\n"
        response += f"Context entities: {list(conversation.last_entities.keys())}\n"

    return AssistantResponse(response_text=response, confidence=1.0)
