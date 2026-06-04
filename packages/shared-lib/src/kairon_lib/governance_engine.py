from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from kairon_lib.utils.sqlite_utils import managed_connection
from typing import Any

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PolicyType enum
# ---------------------------------------------------------------------------


class PolicyType(StrEnum):
    """Type of governance policy."""

    ACCESS_CONTROL = "access_control"
    APPROVAL_FLOW = "approval_flow"
    RESOURCE_QUOTA = "resource_quota"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# PolicyStatus enum
# ---------------------------------------------------------------------------


class PolicyStatus(StrEnum):
    """Status of a governance policy."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Priority enum
# ---------------------------------------------------------------------------


class Priority(StrEnum):
    """Priority level for policy conflict resolution."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# GovernancePolicy dataclass
# ---------------------------------------------------------------------------


@dataclass
class GovernancePolicy:
    """Represents a governance policy with rules."""

    id: str
    name: str
    policy_type: PolicyType
    rules: list[dict[str, object]]
    priority: Priority
    status: PolicyStatus
    created_at: str
    updated_at: str
    version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "policy_type": self.policy_type.value,
            "rules": self.rules,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }


# ---------------------------------------------------------------------------
# ConflictResolution dataclass
# ---------------------------------------------------------------------------


@dataclass
class ConflictResolution:
    """Result of conflict resolution between policies."""

    conflict_id: str
    policy_ids: list[str]
    resolution_strategy: str
    resolved_policy_id: str | None
    reason: str
    resolved_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "policy_ids": self.policy_ids,
            "resolution_strategy": self.resolution_strategy,
            "resolved_policy_id": self.resolved_policy_id,
            "reason": self.reason,
            "resolved_at": self.resolved_at,
        }


# ---------------------------------------------------------------------------
# GovernanceEngine
# ---------------------------------------------------------------------------


class GovernanceEngine:
    """Governance policy execution engine.

    Parses, executes, and resolves conflicts in governance policies.
    Supports YAML/JSON policy definitions with priority-based conflict resolution.

    SQLite at ``data/db/organs/governance/governance_engine.db``.
    Thread-safe; uses a per-instance Lock.

    BOS-URI endpoints
    -----------------
    ``bos://governance/engine/parse``  -- parse a policy document
    ``bos://governance/engine/execute`` -- execute a policy rule
    ``bos://governance/engine/resolve`` -- resolve policy conflicts
    """

    _DEFAULT_DB: str = "data/db/organs/governance/governance_engine.db"
    _lock: threading.Lock
    _priority_order: dict[Priority, int] = {
        Priority.CRITICAL: 4,
        Priority.HIGH: 3,
        Priority.MEDIUM: 2,
        Priority.LOW: 1,
    }

    def __init__(self, db_path: str | None = None) -> None:
        import os

        root = os.environ.get("BOS_ROOT", ".")
        resolved = db_path or self._DEFAULT_DB
        self._db_path = str(Path(root) / resolved)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
        _log.debug("[GovernanceEngine] db=%s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> Any:
        """Get database connection context manager."""
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return managed_connection(conn)

    # ------------------------------------------------------------------
    # Op6 Self-Evolution threshold policy
    # ------------------------------------------------------------------

    def seed_op6_policy(
        self,
        error_threshold: int = 5,
        slow_execution_threshold_ms: int = 1000,
    ) -> GovernancePolicy:
        """Register or update the op6_self_evolution governance policy with threshold values.

        Args:
            error_threshold: Max error count before triggering recurring-error pattern (default 5).
            slow_execution_threshold_ms: Avg execution time (ms) above which slow pattern fires (default 1000).

        Returns:
            The registered GovernancePolicy.
        """
        rules = [
            {
                "name": "error_threshold",
                "value": error_threshold,
                "description": "Max historical error count before recurring-error pattern fires",
            },
            {
                "name": "slow_execution_threshold_ms",
                "value": slow_execution_threshold_ms,
                "description": "Avg execution time (ms) above which slow-execution pattern fires",
            },
        ]
        # Upsert: update if exists, register if not
        policies = self.list_policies(policy_type=None, status=None)
        for policy in policies:
            if policy.name == "op6_self_evolution":
                updated = self.update_policy(policy.id, rules=rules)
                return updated if updated is not None else policy
        return self.register_policy(
            name="op6_self_evolution",
            policy_type=PolicyType.CUSTOM,
            rules=rules,
            priority=Priority.LOW,
        )

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS governance_policies (
                    id              TEXT PRIMARY KEY,
                    name            TEXT NOT NULL,
                    policy_type     TEXT NOT NULL,
                    rules_json      TEXT NOT NULL DEFAULT '[]',
                    priority        TEXT NOT NULL DEFAULT 'MEDIUM',
                    status          TEXT NOT NULL DEFAULT 'PENDING',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    version         INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_type     ON governance_policies(policy_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_status   ON governance_policies(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_policy_priority ON governance_policies(priority)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conflict_resolutions (
                    conflict_id            TEXT PRIMARY KEY,
                    policy_ids_json        TEXT NOT NULL,
                    resolution_strategy    TEXT NOT NULL,
                    resolved_policy_id     TEXT,
                    reason                 TEXT NOT NULL,
                    resolved_at            TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def evaluate_condition(actual: Any, condition_str: str) -> bool:
        """Evaluate a comparison condition against an actual value.

        Supports: ==, !=, >, <, >=, <=

        Args:
            actual: The actual value from context.
            condition_str: Condition specifier, e.g. ">= 5", "== high", "!= 0".

        Returns:
            True if the condition passes, False otherwise.
        """
        import re

        match = re.match(r"^(==|!=|>=|<=|>|<)\s*(.+)$", condition_str.strip())
        if not match:
            return actual == condition_str

        op, raw_value = match.group(1), match.group(2).strip()

        expected: int | float | str
        try:
            expected = int(raw_value)
        except ValueError:
            try:
                expected = float(raw_value)
            except ValueError:
                expected = raw_value

        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected

        return False

    def _row_to_policy(self, row: sqlite3.Row) -> GovernancePolicy:
        return GovernancePolicy(
            id=row["id"],
            name=row["name"],
            policy_type=PolicyType(row["policy_type"]),
            rules=json.loads(row["rules_json"]),
            priority=Priority(row["priority"]),
            status=PolicyStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=row["version"],
        )

    # ------------------------------------------------------------------
    # Public API: Policy Management
    # ------------------------------------------------------------------

    def register_policy(
        self,
        name: str,
        policy_type: PolicyType,
        rules: list[dict[str, object]],
        priority: Priority = Priority.MEDIUM,
    ) -> GovernancePolicy:
        """Register a new governance policy."""
        policy_id = str(uuid.uuid4())
        now = self._now()

        policy = GovernancePolicy(
            id=policy_id,
            name=name,
            policy_type=policy_type,
            rules=rules,
            priority=priority,
            status=PolicyStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO governance_policies
                    (id, name, policy_type, rules_json, priority, status, created_at, updated_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy.id,
                    policy.name,
                    policy.policy_type.value,
                    json.dumps(policy.rules),
                    policy.priority.value,
                    policy.status.value,
                    policy.created_at,
                    policy.updated_at,
                    policy.version,
                ),
            )
            conn.commit()

        _log.debug("[GovernanceEngine] registered policy %s", policy_id)
        return policy

    def get_policy(self, policy_id: str) -> GovernancePolicy | None:
        """Retrieve a policy by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM governance_policies WHERE id = ?", (policy_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_policy(row)

    def list_policies(
        self, policy_type: PolicyType | None = None, status: PolicyStatus | None = None
    ) -> list[GovernancePolicy]:
        """List policies with optional filters."""
        clauses: list[str] = []
        params: list = []

        if policy_type is not None:
            clauses.append("policy_type = ?")
            params.append(policy_type.value)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM governance_policies {where} ORDER BY priority DESC, created_at DESC",
                params,
            ).fetchall()

        return [self._row_to_policy(r) for r in rows]

    def update_policy(self, policy_id: str, rules: list[dict[str, object]] | None = None) -> GovernancePolicy | None:
        """Update policy rules and increment version."""
        policy = self.get_policy(policy_id)
        if policy is None:
            return None

        if rules is not None:
            policy.rules = rules

        policy.version += 1
        policy.updated_at = self._now()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE governance_policies
                SET rules_json = ?, updated_at = ?, version = ?
                WHERE id = ?
                """,
                (json.dumps(policy.rules), policy.updated_at, policy.version, policy_id),
            )
            conn.commit()

        _log.debug("[GovernanceEngine] updated policy %s to v%d", policy_id, policy.version)
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy by ID."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM governance_policies WHERE id = ?", (policy_id,))
            conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            _log.debug("[GovernanceEngine] deleted policy %s", policy_id)
        return deleted

    # ------------------------------------------------------------------
    # Public API: Policy Execution
    # ------------------------------------------------------------------

    def parse_policy(self, policy_data: str | dict) -> GovernancePolicy:
        """Parse a policy from YAML/JSON string or dict."""
        if isinstance(policy_data, str):
            try:
                data = json.loads(policy_data)
            except json.JSONDecodeError:
                # Try YAML if available
                try:
                    import yaml

                    data = yaml.safe_load(policy_data)
                except ImportError:
                    raise ValueError("YAML support requires PyYAML") from None
                except yaml.YAMLError as exc:
                    raise ValueError(f"Invalid policy YAML: {exc}") from exc
        else:
            data = policy_data

        policy_type = PolicyType(data.get("type", "custom"))
        rules = data.get("rules", [])
        priority = Priority(data.get("priority", "medium"))
        name = data.get("name", f"policy_{uuid.uuid4().hex[:8]}")

        return self.register_policy(name, policy_type, rules, priority)

    def execute_rule(self, policy_id: str, rule_index: int, context: dict[str, object]) -> dict[str, object]:
        """Execute a single rule from a policy."""
        policy = self.get_policy(policy_id)
        if policy is None:
            raise ValueError(f"Policy {policy_id} not found")

        if rule_index < 0 or rule_index >= len(policy.rules):
            raise IndexError(f"Rule index {rule_index} out of bounds")

        rule = policy.rules[rule_index]
        rule_type: Any = rule.get("type", "condition")
        conditions: Any = rule.get("conditions", {})
        actions: Any = rule.get("actions", [])

        result = {
            "policy_id": policy_id,
            "rule_index": rule_index,
            "rule_type": rule_type,
            "matched": True,
            "actions_executed": [],
            "timestamp": self._now(),
        }

        # Evaluate conditions -- supports ==, !=, >, <, >=, <=
        for key, condition_spec in conditions.items():
            actual = context.get(key)
            if not self.evaluate_condition(actual, str(condition_spec)):
                result["matched"] = False
                result["reason"] = f"Condition failed: {key}={actual}, condition={condition_spec}"
                break

        # Execute actions if matched
        if result["matched"]:
            for action in actions:
                action_type = action.get("type")
                action_params = action.get("params", {})
                result["actions_executed"].append({"type": action_type, "params": action_params})

        _log.debug(
            "[GovernanceEngine] executed rule %d from policy %s: matched=%s",
            rule_index,
            policy_id,
            result["matched"],
        )
        return result

    # ------------------------------------------------------------------
    # Public API: Conflict Resolution
    # ------------------------------------------------------------------

    def resolve_conflicts(self, policy_ids: list[str], strategy: str = "priority") -> ConflictResolution:
        """Resolve conflicts between policies using the specified strategy.

        Strategies:
        - 'priority': use highest priority policy
        - 'newest': use most recently updated policy
        - 'merge': attempt to merge rules (experimental)
        """
        conflict_id = str(uuid.uuid4())
        policies = [p for pid in policy_ids if (p := self.get_policy(pid)) is not None]

        if not policies:
            raise ValueError("No valid policies found for conflict resolution")

        resolved_policy: GovernancePolicy | None = None
        reason = ""

        if strategy == "priority":
            resolved_policy = max(policies, key=lambda p: self._priority_order.get(p.priority, 0))
            reason = f"Resolved by priority: {resolved_policy.priority.value}"
        elif strategy == "newest":
            resolved_policy = max(policies, key=lambda p: p.updated_at)
            reason = f"Resolved by newest update: {resolved_policy.updated_at}"
        elif strategy == "merge":
            # Experimental: merge rules from all policies
            merged_rules = []
            for p in policies:
                merged_rules.extend(p.rules)

            merged = self.register_policy(
                name=f"merged_{conflict_id[:8]}",
                policy_type=PolicyType.CUSTOM,
                rules=merged_rules,
                priority=max(p.priority for p in policies),
            )
            resolved_policy = merged
            reason = f"Merged {len(policies)} policies into {merged.id}"
        else:
            raise ValueError(f"Unknown resolution strategy: {strategy}")

        resolution = ConflictResolution(
            conflict_id=conflict_id,
            policy_ids=policy_ids,
            resolution_strategy=strategy,
            resolved_policy_id=resolved_policy.id if resolved_policy else None,
            reason=reason,
            resolved_at=self._now(),
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conflict_resolutions
                    (conflict_id, policy_ids_json, resolution_strategy, resolved_policy_id, reason, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolution.conflict_id,
                    json.dumps(resolution.policy_ids),
                    resolution.resolution_strategy,
                    resolution.resolved_policy_id,
                    resolution.reason,
                    resolution.resolved_at,
                ),
            )
            conn.commit()

        _log.info(
            "[GovernanceEngine] resolved conflict %s using strategy '%s'",
            conflict_id,
            strategy,
        )
        return resolution
