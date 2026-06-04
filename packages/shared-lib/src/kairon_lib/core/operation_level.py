"""Operation Level Enforcement — MCP tool 操作分级拒绝路径。

提供可复用的装饰器和中间件，为 MCP tool 添加 L0-L3 操作分级检查。

用法:
    from kairon_lib.operation_level import operation_level, OpLevel

    @mcp.tool()
    @operation_level(OpLevel.L2, human_approval=True)
    def delete_page(slug: str, _confirmed: bool = False) -> dict:
        ...
"""

from __future__ import annotations

import functools
import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

_log = logging.getLogger(__name__)

AUDIT_LOG_DIR = os.environ.get(
    "OMOSTATION_AUDIT_DIR",
    os.path.expanduser("~/.omostation/audit"),
)


class OpLevel(IntEnum):
    """L0-L3 操作分级，值与标准文档一致。"""

    READ = 0  # L0: 读操作，无副作用
    LOW_RISK = 1  # L1: 低风险写，审计记录即可
    HIGH_RISK = 2  # L2: 高风险写，需人工确认
    DESTRUCTIVE = 3  # L3: 破坏性操作，需确认 + 24h 冷静期


def _ensure_audit_dir() -> None:
    """确保审计日志目录存在。"""
    os.makedirs(AUDIT_LOG_DIR, exist_ok=True)


def _write_audit(entry: dict) -> None:
    """写入审计日志条目。"""
    _ensure_audit_dir()
    log_path = os.path.join(AUDIT_LOG_DIR, "operations.log")
    entry["timestamp"] = datetime.now(UTC).isoformat()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_operation_level(
    level: int | OpLevel,
    tool_name: str,
    args: dict[str, Any],
    actor: str = "unknown",
) -> None:
    """检查操作级别，拒绝未确认的 L2/L3 操作。

    Args:
        level: 操作级别 (0-3)
        tool_name: 工具名称
        args: 调用参数（会被修改以移除 _confirmed/_cool_down_hours）
        actor: 调用者标识

    Raises:
        PermissionError: 如果级别检查未通过
    """
    level = int(level)

    # L0/L1: 自动允许
    action = "allow"
    reason = "auto-approved"

    if level >= 2:
        confirmed = args.pop("_confirmed", False)
        if not confirmed:
            action = "deny"
            reason = f"L{level} operation '{tool_name}' requires explicit confirmation. Re-run with `_confirmed: true`."
            _write_audit(
                {
                    "operation_level": level,
                    "tool": tool_name,
                    "action": "deny",
                    "actor": actor,
                    "reason": reason,
                }
            )
            raise PermissionError(reason)

    if level >= 3:
        cooldown = args.pop("_cool_down_hours", 0)
        if cooldown < 24:
            action = "deny"
            reason = (
                f"L3 operation '{tool_name}' requires explicit confirmation "
                f"AND 24h cool-down. Set `_cool_down_hours: 24`."
            )
            _write_audit(
                {
                    "operation_level": level,
                    "tool": tool_name,
                    "action": "deny",
                    "actor": actor,
                    "reason": reason,
                }
            )
            raise PermissionError(reason)

    # 写入审计日志
    _write_audit(
        {
            "operation_level": level,
            "tool": tool_name,
            "action": action,
            "actor": actor,
            "reason": reason,
        }
    )


def operation_level(
    level: int | OpLevel,
    human_approval: bool = False,
) -> Callable:
    """装饰器：为 MCP tool 函数添加操作分级检查。

    Args:
        level: 操作级别 (OpLevel.READ/LOW_RISK/HIGH_RISK/DESTRUCTIVE)
        human_approval: 是否要求人工审批（L2+ 默认需要）

    Usage:
        @mcp.tool()
        @operation_level(OpLevel.HIGH_RISK)
        def delete_page(slug: str, _confirmed: bool = False) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 提取 actor（如果有）
            actor = kwargs.pop("_actor", os.environ.get("USER", "unknown"))
            # 检查级别
            check_operation_level(level, func.__name__, kwargs, actor=actor)
            # 通过后执行原函数
            return func(*args, **kwargs)

        # 保存级别元数据，供 registry 注册时读取
        wrapper._operation_level = int(level)  # type: ignore[attr-defined]
        wrapper._human_approval = human_approval  # type: ignore[attr-defined]
        return wrapper

    return decorator
