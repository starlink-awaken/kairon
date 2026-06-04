# Kairon Cross-Project Boundary Audit

> Scope: `kairon <-> agentmesh`, `kairon <-> SharedBrain`, `kairon <-> .omo`
> Audit date: 2026-06-04

## 1. `kairon <-> agentmesh`

### Live evidence

- `/Users/xiamingxing/Workspace/projects/agentmesh/README.md` states the project is archived and **100% migrated to kairon**
- the migration table maps:
  - Engine -> `packages/agent-runtime/`
  - Agent Registry -> `packages/agent-hub/`
  - Gateway -> `packages/agora/`
  - Toolkit -> `packages/forge/`
  - Model-Orchestrator -> `packages/llm-gateway/`

### Audit finding

The declared migration target is internally inconsistent with the live tree.

- `agent-runtime`, `agora`, `forge`, `llm-gateway` exist
- `agent-hub` does **not** exist in the current live `packages/` inventory

### Implication

The migration story is only partially trustworthy. Any architecture conclusion that assumes "agentmesh migration complete" without reconciling the missing `agent-hub` target is overstated.

### Required remediation

- confirm whether `agent-hub` was deleted, merged, or never landed in this checkout
- update the agentmesh migration map after the repo-side truth is fixed

## 2. `kairon <-> SharedBrain`

### Live evidence

- current `projects/` tree has no `projects/SharedBrain/`
- `packages/sharedbrain-bridge/README.md` still describes a bridge between `kairon` and `SharedBrain`
- `.omo/_truth/INVENTORY.md` still models `projects/SharedBrain/` as a live workspace project

### Audit finding

The bridge package still exists, but the sibling-project boundary it is supposed to bridge is no longer present in the live tree.

### Implication

There are only two coherent possibilities:

1. `SharedBrain` is now an externalized runtime/data concept, not a sibling repo
2. the workspace inventory is stale and the repo structure is incomplete

Until that is resolved, `sharedbrain-bridge` is semantically under-specified.

### Required remediation

- rewrite `sharedbrain-bridge` package docs around the actual upstream contract
- stop describing `SharedBrain` as a live repo if it is no longer in the working tree

## 3. `kairon <-> .omo`

### Live evidence

- `.omo/_truth/INVENTORY.md` still claims:
  - 5 embedded subrepos including `SharedBrain`
  - `kairon` has 31 Python packages
- several `.omo` standards and tests still reference `projects/SharedBrain/` and older agentmesh topology
- current `.omo/state/system.yaml` is already on phase 26, so older phase-level narratives are not the live operating truth anymore

### Audit finding

`.omo` is currently a mixed-quality governance layer:

- strong at preserving prior decisions and historical rollout traces
- weak as a current inventory authority for `kairon`

### Implication

If `.omo` is allowed to keep stale topology facts while `kairon` evolves quickly, governance will overstate system readiness and understate repo debt.

### Required remediation

- do not mirror the full audit report into `.omo`
- register only evidence pointers and remediation tasks in `.omo`
- update `.omo` inventory claims only after repo-side package truth is confirmed

## 4. Boundary Risk Summary

| Seam | Risk | Why |
|---|---|---|
| `kairon <-> agentmesh` | P0 | migration map points to at least one missing target |
| `kairon <-> SharedBrain` | P1 | bridge exists but upstream project boundary is stale |
| `kairon <-> .omo` | P0 | governance inventory is no longer a trustworthy live topology source |

