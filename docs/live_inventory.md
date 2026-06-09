# Kairon Live Inventory

> Scope: `/Users/xiamingxing/Workspace/projects/kairon`
> Snapshot date: 2026-06-07
> Method: `packages/*/pyproject.toml` live scan + source/test file counting

## Summary

- Live installable packages: **16**
- Truth source: package directories that currently contain `pyproject.toml`
- Main drift: repo docs still describe 19/25/31-package states that no longer match the working tree

## Installable Packages

| Package dir | Project name | Version | Python | Source `.py` | Test files | Role |
|---|---|---:|---|---:|---:|---|
| `codeanalyze` | `codeanalyze` | 0.5.0 | `>=3.10` | 75 | 13 | code and structure analysis |
| `core-models` | `core-models` | 0.5.0 | `>=3.10` | 17 | 6 | shared base models |
| `eidos` | `eidos` | 0.5.0 | `>=3.10` | 143 | 24 | schema and contract layer |
| `forge` | `forge` | 1.3.0 | `>=3.10` | 44 | 11 | tooling and marketplace surface |
| `health-profile` | `health-profile` | 0.1.0 | `>=3.10` | 4 | 1 | health summarization helpers |
| `iris` | `iris` | 0.3.0 | `>=3.10` | 47 | 10 | research/connectors support |
| `kairon-lib-events` | `kairon-lib-events` | 0.4.0 | `>=3.10` | 1 | 1 | event primitives |
| `kairon-observability` | `kairon-observability` | 0.4.0 | `>=3.10` | 7 | 2 | observability helpers |
| `kairon-pipeline` | `kairon-pipeline` | 0.4.0 | `>=3.10` | 8 | 2 | pipeline helpers |
| `kairon-plugin-sdk` | `kairon-plugin-sdk` | 0.4.0 | `>=3.10` | 4 | 1 | plugin integration surface |
| `kairon-utils` | `kairon-utils` | 0.4.0 | `>=3.10` | 12 | 10 | shared utility layer |
| `kos` | `kos` | 2.0.0 | `>=3.10` | 83 | 23 | cross-search and retrieval |
| `kronos` | `kronos` | 0.7.0 | `>=3.10` | 15 | 9 | ingest pipeline |
| `minerva` | `minerva` | 0.15.0 | `>=3.10` | 144 | 37 | deep research and knowledge pipeline |
| `ontoderive` | `ontoderive` | 3.6.4 | `>=3.10` | 20 | 48 | ontology derivation |
| `sophia` | `sophia` | 1.0.0 | `>=3.10` | 10 | 2 | symbolic research runtime |

## Workspace Drift

### Historical or missing members still referenced elsewhere

These names are still present in docs, route aliases, or workspace exclude lists, but they are **not live installable packages** in the current tree:

- `engine-core`
- `sharedbrain-bridge`
- `ssot`
- `symphony-protocol`
- `llm-gateway`
- `protocols-layer`
- `sot-bridge`

### `tool.uv.workspace.exclude` drift

`pyproject.toml` still excludes six historical members:

- `packages/sophia`
- `packages/symphony-protocol`
- `packages/ssot`
- `packages/sharedbrain-bridge`
- `packages/llm-gateway`
- `packages/engine-core`

Observed live state on 2026-06-07:

- `sophia` still exists and is installable
- the other five paths no longer exist as package directories

This means the workspace config is carrying compatibility debris from earlier topology states.

## Current Reading of the Repo

The repo is no longer a broad "all-in-one" runtime surface. It is now mostly:

1. foundational package shards: `core-models`, `kairon-*`, `health-profile`
2. knowledge engines: `eidos`, `kos`, `kronos`, `minerva`, `ontoderive`, `iris`, `sophia`, `codeanalyze`
3. one outward-facing capability surface: `forge`

Everything else that used to represent gateway, bridge, SSOT, or operator-home responsibilities has either moved to sibling projects or survives only as route-level historical aliases.
