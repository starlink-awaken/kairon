# Kairon Architecture Audit v2

> Scope: `/Users/xiamingxing/Workspace/projects/kairon`
> Audit date: 2026-06-04
> Method: live directory scan, `pyproject.toml` parsing, git history spot-check, `make test-fast` smoke run

## Executive Summary

This repo is not in the shape its own docs describe.

- The live working tree contains **25 installable packages** under `packages/*/pyproject.toml`, not the repeatedly documented 26 or 31.
- The workspace root still treats `packages/*` as a clean UV workspace, but the directory is polluted by **three non-package members**: `agora.db`, `agora-audit.db`, `kairon-10pkg-analysis.md`.
- `make test-fast` is not clean. The first high-signal failures are:
  - `agent-runtime`: `ModuleNotFoundError: fastapi`
  - `agora`: MCP registry mismatch, semantic router degraded by missing `sentence_transformers`, pipeline event payload shape regression
- Cross-project truth is also drifting:
  - `projects/agentmesh/README.md` declares it is **100% migrated to kairon**
  - `.omo/_truth/INVENTORY.md` still models `agentmesh` and `SharedBrain` as active first-class projects and still claims `kairon` has 31 packages
  - the live `projects/` tree no longer contains `projects/SharedBrain/`

Conclusion: the main risk is no longer "missing features". It is **loss of trustworthy topology**. Before adding more capability, the repo needs a credible inventory, a clean workspace boundary, and repaired runtime contracts around `agora`, `wksp`, `sharedbrain-bridge`, and `agent-runtime`.

## 1. Evidence Baseline

### 1.1 Package inventory

Live scan result: **25 package directories** with `pyproject.toml`.

`agent-runtime`, `agora`, `codeanalyze`, `core-models`, `cron-service`, `ecos`, `eidos`, `engine-core`, `forge`, `iris`, `kairon-assistant`, `kairon-voice`, `kaironcloud-billing`, `kos`, `kronos`, `llm-gateway`, `metaos`, `minerva`, `ontoderive`, `shared-lib`, `sharedbrain-bridge`, `sophia`, `ssot`, `symphony-protocol`, `wksp`

### 1.2 Workspace noise under `packages/`

The UV workspace emits warnings for these non-directory members:

- `packages/agora.db`
- `packages/agora-audit.db`
- `packages/kairon-10pkg-analysis.md`

This is not cosmetic. It means the workspace boundary is already leaking runtime residue and analysis artifacts into the package plane.

### 1.3 Sampled test baseline

Read-only smoke run: `cd /Users/xiamingxing/Workspace/projects/kairon && make test-fast`

Observed failures:

- `agent-runtime`
  - 4 failed, 218 passed, 16 skipped
  - `src/agent_runtime/server.py` imports `fastapi`, but the test environment used by the workspace target cannot satisfy that contract
- `agora`
  - 8 failed, 1185 passed, 3 skipped
  - known services list missing `kronos`
  - semantic router returns empty results when embeddings backend is unavailable (`sentence_transformers` missing)
  - pipeline event payload tests fail because payload is a `str` where tests expect a mapping

These are product contract failures and environment-contract failures mixed together. They must be classified separately instead of being flattened into "tests unstable".

## 2. Real Topology

### 2.1 Functional layers

The current repo is better understood as five layers, not as a flat bag of packages.

| Layer | Packages | Notes |
|---|---|---|
| Foundation and shared primitives | `core-models`, `shared-lib`, `symphony-protocol` | `core-models` is the only clear dependency base; `shared-lib` is large but not used as a declared internal hub |
| Runtime and entry surfaces | `agora`, `wksp`, `agent-runtime`, `cron-service`, `metaos`, `engine-core` | This is where surface overlap is concentrated |
| Knowledge and reasoning | `eidos`, `kos`, `minerva`, `ontoderive`, `ssot`, `sophia`, `ecos` | This is the densest capability band |
| Ingestion, connectors, analysis | `kronos`, `iris`, `codeanalyze`, `forge` | In practice these feed the knowledge/runtime layers |
| Product and bridge surfaces | `sharedbrain-bridge`, `llm-gateway`, `kairon-assistant`, `kairon-voice`, `kaironcloud-billing` | These expose seams to external systems or end-user workflows |

### 2.2 Topology facts that contradict existing docs

- `core-models` is a real base package, but it is **not** sufficient to explain the runtime architecture.
- `wksp` is not yet proven to be the single operator entrypoint; it currently reads more like another package CLI layered beside `agora`.
- `sharedbrain-bridge` exists, but the repo-level `SharedBrain` project no longer exists in the current `projects/` tree.
- git history since 2026-06-01 still references packages that are absent from the working tree: `agent-hub`, `eu-pricing`, `gc-engine`, `observability`, `pontus`, `sharedbrain-standalone`. This is a strong drift signal between documented topology, recent history, and live checkout.

## 3. Inventory Table

### 3.1 Recomputed package metrics

| Package | Version | Python | Source `.py` | Test files | Declared internal deps |
|---|---:|---:|---:|---:|---|
| agent-runtime | 0.5.0 | >=3.10 | 108 | 15 | - |
| agora | 2.0.0 | >=3.11 | 155 | 46 | `core-models`, `eidos`, `kos`, `minerva` |
| codeanalyze | 0.5.0 | >=3.10 | 63 | 13 | `core-models`, `eidos` |
| core-models | 0.5.0 | >=3.10 | 17 | 3 | - |
| cron-service | 1.0.0 | >=3.10 | 11 | 3 | - |
| ecos | 0.8.0 | >=3.10 | 19 | 8 | - |
| eidos | 0.5.0 | >=3.10 | 133 | 24 | `core-models` |
| engine-core | 0.3.0 | >=3.10 | 130 | 10 | - |
| forge | 1.3.0 | >=3.10 | 28 | 11 | - |
| iris | 0.3.0 | >=3.10 | 46 | 10 | `eidos`, `kronos`, `minerva` |
| kairon-assistant | 1.0.0 | >=3.10 | 9 | 3 | - |
| kairon-voice | 1.0.0 | >=3.10 | 8 | 3 | - |
| kaironcloud-billing | 0.2.0 | >=3.11 | 28 | 5 | - |
| kos | 2.0.0 | >=3.10 | 84 | 23 | `eidos` |
| kronos | 0.7.0 | >=3.10 | 15 | 9 | `core-models` |
| llm-gateway | 0.3.0 | >=3.10 | 27 | 4 | `minerva` |
| metaos | 7.1.0 | >=3.10 | 29 | 11 | - |
| minerva | 0.15.0 | >=3.10 | 121 | 34 | `core-models`, `kos` |
| ontoderive | 3.6.4 | >=3.10 | 134 | 48 | `core-models` |
| shared-lib | 0.4.0 | >=3.10 | 303 | 34 | - |
| sharedbrain-bridge | 0.2.0 | >=3.10 | 8 | 4 | `core-models` |
| sophia | 0.3.0 | >=3.10 | 10 | 6 | `core-models` |
| ssot | 1.0.0 | >=3.10 | 53 | 10 | - |
| symphony-protocol | 0.1.0 | >=3.10 | 5 | 5 | - |
| wksp | 0.3.0 | >=3.10 | 16 | 42 | - |

### 3.2 Maturity scoring

Scoring rule: each package gets 0-2 points on four axes.

- `test_state`: observed test footprint only
- `surface`: scripts or explicit operator/runtime surface
- `inbound`: number of other live packages declaring it as a dependency
- `heat`: recent git touch count since 2026-06-01

This is not a quality score. It is an **operational maturity signal**.

| Tier | Packages | Why they land here |
|---|---|---|
| 8/8 | `eidos`, `minerva` | broad surface, inbound usage, heavy recent churn, non-trivial tests |
| 7/8 | `kos` | real entry surface plus meaningful tests and inbound coupling |
| 6/8 | `agora`, `ontoderive` | high heat and surface breadth, but inbound coupling is weaker than docs imply |
| 5/8 | `agent-runtime`, `codeanalyze`, `iris`, `kronos`, `shared-lib`, `wksp` | useful surfaces exist, but either coupling or baseline quality is still thin |
| 4/8 | `ecos`, `engine-core`, `forge`, `kaironcloud-billing`, `metaos`, `sophia` | active but not yet trustworthy anchors |
| 3/8 | `core-models`, `cron-service`, `sharedbrain-bridge`, `ssot` | important names, but either test posture or actual adoption signal is weaker than expected |
| 2/8 | `llm-gateway` | still a thin seam, not yet a stable unifying layer |
| 1/8 | `kairon-assistant`, `kairon-voice`, `symphony-protocol` | low test signal, low adoption signal, minimal visible surface |

The old `Stable/Beta` labels are not defendable anymore. These scores are.

## 4. Dependency and Coupling Audit

### 4.1 Declared internal dependency spine

The actual declared spine is much narrower than the previous docs claimed.

- `core-models` has the highest inbound dependency count
- `eidos`, `kos`, and `minerva` form the only clearly visible knowledge/runtime dependency cluster
- many packages are effectively standalone from a packaging perspective, even when the docs describe them as integrated subsystems

### 4.2 Coupling types that matter

There are three different kinds of coupling here, and the repo has been mixing them together.

1. Packaging coupling
   - `project.dependencies` internal references
2. Runtime coupling
   - HTTP services, MCP servers, registry membership, event bus payloads
3. Operator coupling
   - CLI surfaces, scripts, workflow expectations, `.omo` governance references

`agora` is central mainly in categories 2 and 3, not because the Python package graph proves it is central.

### 4.3 Hot spots

- `agora`: registry, routing, event bus, and cross-package exposure all converge here
- `wksp`: claims workspace-level role but has not yet displaced other entrypoints
- `sharedbrain-bridge`: name implies a stable upstream project boundary that is no longer present in the live `projects/` tree
- `llm-gateway`: still too thin to claim unification
- `agent-runtime`: significant source footprint, but broken environment contract under smoke test

## 5. Interface and Contract Audit

### 5.1 MCP / service registry

`agora` is failing the exact kind of contract it is supposed to stabilize.

- known services bootstrap is missing `kronos`
- semantic routing degrades to empty results if embeddings support is absent
- pipeline event payloads are shape-incompatible with their tests

That is not one bug. That is one control surface failing in three separate modes:
registry truth, degraded routing truth, and event schema truth.

### 5.2 CLI and operator surface

The repo currently exposes multiple competing operator surfaces:

- `agora`
- `wksp`
- `kos`
- `agent-runtime`
- package-local CLIs like `minerva`, `kronos`, `forge`

The architecture has not yet earned the claim that there is one operator home. `wksp` may be intended to play that role, but the current repo does not prove it.

### 5.3 Bridge boundary

`sharedbrain-bridge` is nominally a bridge between `kairon` and `SharedBrain`, but:

- live `projects/` no longer contains `projects/SharedBrain/`
- package README is minimal and does not define a current contract
- `.omo` still references old `SharedBrain` roots in multiple places

So the bridge exists, but the upstream boundary it points to is no longer well modeled.

## 6. Engineering Quality Audit

### 6.1 Version and Python drift

- root repo requires Python `>=3.10`
- individual packages mostly say `>=3.10`, but `agora` and `kaironcloud-billing` require `>=3.11`
- root Ruff target is `py313`

This is survivable, but it is not yet a clearly governed contract. The repo needs one documented support matrix instead of implicit drift.

### 6.2 Test signal quality

The test count distribution is highly uneven.

- heavy test surfaces: `agora`, `ontoderive`, `wksp`, `minerva`, `shared-lib`, `eidos`, `kos`
- thin but non-zero: many packages in the 3-13 range
- nearly symbolic: `core-models`, `cron-service`, `kairon-assistant`, `kairon-voice`

The current smoke run shows two failure categories:

| Class | Observed examples |
|---|---|
| `dependency_misaligned` | `agent-runtime` missing `fastapi` at test time |
| `contract_regression` | `agora` registry mismatch, router no-result regression, event payload shape mismatch |
| `env_missing` | semantic routing degraded when `sentence_transformers` is absent |
| `design_smell` | package workspace polluted by DB and analysis artifacts |

## 7. Cross-Project Boundary Findings

This audit includes cross-project seams because the package-level picture alone is misleading.

- `agentmesh` says its runtime, gateway, toolkit, and LLM provider roles moved into `kairon`
- the migration map names `packages/agent-hub/`, but that package is absent from the current live tree
- `.omo` still carries stale topology assumptions about `SharedBrain`, `agentmesh`, and package counts

Detailed seam analysis lives in `docs/cross_project_boundary_audit.md`.

## 8. Risk Grading

### P0

- Inventory and documentation drift across repo and `.omo`
- `packages/` boundary pollution
- `agora` contract regressions
- `agent-runtime` test/runtime dependency mismatch

### P1

- unclear operator-home split between `wksp`, `agora`, `kos`, and package-local CLIs
- stale `sharedbrain-bridge` boundary model
- incomplete `llm-gateway` unification story

### P2

- broader package taxonomy cleanup
- git history and live checkout reconciliation for removed or migrated packages
- `.omo` truth sync after repo-side contracts are repaired

## 9. Recommended Route

1. Rebuild and publish a single authoritative package inventory inside this repo.
2. Clean `packages/` so UV workspace membership is trustworthy again.
3. Repair `agora` in this order:
   - service registry truth
   - event payload schema
   - degraded semantic routing behavior
4. Decide whether `wksp` is the operator home or just another CLI.
5. Re-document `sharedbrain-bridge` against the live reality that `SharedBrain` is no longer a live sibling repo in `projects/`.
6. Only after that, sync `.omo` inventory and capability claims.

## 10. Verification Evidence

- live scan of `packages/*/pyproject.toml`
- recomputed source/test/dependency metrics from package manifests and file trees
- git touch counts since 2026-06-01
- `make test-fast` smoke evidence capturing `agent-runtime` and `agora` failures
- cross-check against:
  - `/Users/xiamingxing/Workspace/projects/kairon/README.md`
  - `/Users/xiamingxing/Workspace/projects/kairon/AGENTS.md`
  - `/Users/xiamingxing/Workspace/projects/agentmesh/README.md`
  - `/Users/xiamingxing/Workspace/.omo/_truth/INVENTORY.md`

