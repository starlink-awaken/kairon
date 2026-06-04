# EXTRACTED.md — D_Governance Zero-Coupling Migration to kairon/shared-lib

**Date**: 2026-06-01
**Source**: SharedBrain `organs/D_Governance/`
**Target**: kairon `packages/shared-lib/src/kairon_lib/`
**Tests**: kairon `packages/shared-lib/tests/`

---

## Extraction Summary

| # | Source File | Lines | Target Module | Extraction Strategy |
|---|-------------|-------|---------------|---------------------|
| 1 | `organs/governance/ai/thinking_paths.py` | 763 | `thinking.py` | Full extraction (zero coupling) |
| 2 | `organs/compliance/permission_matrix.py` | 696 | `rbac.py` | Dataclasses/enums only (SQLite skipped) |
| 3 | `organs/role/role_rbac.py` | 268 | `rbac.py` | Dataclasses only (SQLite skipped) |
| 4 | `organs/role/role_slo_registry.py` | 145 | `slo.py` | Full extraction (zero coupling) |
| 5 | `organs/lifecycle/rfc_lifecycle_manager.py` | 151 | `lifecycle.py` | Dataclasses/enum/transitions only (BaseMembrane skipped) |

---

## What Was Extracted

### 1. `thinking.py` — Thinking Path Library

| Symbol | Type | Description |
|--------|------|-------------|
| `ThinkingMode` | StrEnum | 17 reasoning modes (council, red_team, socratic, first_principles, ...) |
| `ReasoningMode` | alias | `ReasoningMode = ThinkingMode` (backward compat) |
| `ThinkingStep` | dataclass | Single reasoning step with mode, prompt, output format |
| `ThinkingPath` | dataclass | Ordered sequence of steps with render/to_dict/summary methods |
| `first_principles_path()` | factory | Conductor-style: decompose to fundamentals |
| `adversarial_review_path()` | factory | Conductor-style: red-team a proposal |
| `constraint_first_path()` | factory | Conductor-style: map constraints first |
| `multi_perspective_path()` | factory | Conductor-style: gather diverse viewpoints |
| `scientific_validation_path()` | factory | Conductor-style: hypothesis-driven |
| `retrospective_extraction_path()` | factory | Conductor-style: extract principles |
| `creative_divergence_path()` | factory | Conductor-style: maximize creative space |
| `ThinkingPathLibrary` | class | Registry + 7 nucleus-style static constructors + recommend/from_mode |

### 2. `rbac.py` — Combined RBAC Model

**From permission_matrix.py:**

| Symbol | Type | Description |
|--------|------|-------------|
| `PermissionAction` | StrEnum | READ, WRITE, EXECUTE, ADMIN |
| `Effect` | StrEnum | ALLOW, DENY |
| `ActionType` | StrEnum | READ, WRITE, DELETE, EXECUTE, ADMIN, CUSTOM |
| `PermissionRule` | dataclass | Role + resource_pattern + actions + effect binding |
| `RoleDefinition` | dataclass | Role with permissions and optional parent |
| `Permission` | dataclass | Full permission entry with audit trail + conditions |
| `RoleInheritance` | dataclass | Child-parent role inheritance link |
| `PermissionConflict` | dataclass | Detected allow/deny or cycle conflict |

**From role_rbac.py (renamed for disambiguation):**

| Symbol | Type | Description |
|--------|------|-------------|
| `AccessRule` | dataclass | Simple resource-to-actions permission rule (was `Permission`) |
| `RolePermissionSet` | dataclass | Role rules + EU budget + time window |
| `AccessDecision` | dataclass | allowed/reason result |
| `AuditEntry` | dataclass | Access check audit record |

**What was skipped:**
- `PermissionMatrix` class (SQLite + threading orchestration, depends on `nucleus.Z_Microkernel.utilities.sqlite_utils`)
- `RoleRBAC` class (SQLite + threading orchestration)
- `managed_connection` import from nucleus (external dependency)

### 3. `slo.py` — Role SLO Registry

| Symbol | Type | Description |
|--------|------|-------------|
| `RoleSLO` | dataclass | SLO bound to a role (target metric + window) |
| `RoleSLOViolation` | dataclass | Recorded violation event |
| `RoleSLORegistry` | class | In-memory registry: register, record, check compliance, at-risk surfacing |

Full extraction — zero external dependencies (only `time` + `dataclasses`).

### 4. `lifecycle.py` — RFC Lifecycle Types

| Symbol | Type | Description |
|--------|------|-------------|
| `RFCState` | Enum | 7 states: DRAFT, OPEN, REVIEWING, APPROVED, REJECTED, ENFORCED, WITHDRAWN |
| `VALID_TRANSITIONS` | dict | Legal state transition map |
| `TERMINAL_STATES` | frozenset | Terminal states (ENFORCED, WITHDRAWN) |
| `ENTRANCE_STATES` | frozenset | Entrance states (DRAFT) |
| `RFC` | dataclass | RFC data model with `create()` factory + `can_transition_to()` / `is_terminal()` |
| `is_valid_transition()` | function | Check if state transition is legal |
| `is_terminal()` | function | Check if state is terminal |

**What was skipped:**
- `RFCLifecycleManager` class (inherits from `BaseMembrane`, contains orchestration logic)

---

## Naming Disambiguation

The two source files had conflicting `Permission` dataclass names:

| Original location | Original name | New name in rbac.py | Fields |
|---|---|---|---|
| `permission_matrix.py` | `Permission` | `Permission` (unchanged) | id, role_id, resource, action, effect, granted_at, granted_by, inherited_from, conditions |
| `role_rbac.py` | `Permission` | `AccessRule` | resource, actions (list[str]) |

---

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_thinking.py` | 39 | ThinkingMode, ThinkingStep, ThinkingPath, 7 factories, library registry + nucleus constructors |
| `tests/test_rbac.py` | 26 | PermissionAction, Effect, ActionType, PermissionRule, RoleDefinition, Permission, RoleInheritance, PermissionConflict, AccessRule, RolePermissionSet, AccessDecision, AuditEntry |
| `tests/test_slo.py` | 24 | RoleSLO, RoleSLOViolation, RoleSLORegistry (register, record, compliance, violations, at-risk, window filtering) |
| `tests/test_lifecycle.py` | 29 | RFCState, VALID_TRANSITIONS, is_valid_transition, is_terminal, RFC (create, transitions, terminal), full lifecycle paths |
| **Total** | **118** (new) | 147 total with existing tests |

---

## Pre-existing Issues Fixed

During this extraction, the `__init__.py` in `kairon_lib` was found broken (importing non-existent names `OperationLevel` and `URIModel`). Fixed to use the correct names `OpLevel` and `UriResource`.

---

## Verification

```bash
cd packages/shared-lib && PYTHONPATH=src python3 -m pytest tests/ -v
# Result: 147 passed in 1.23s
```
