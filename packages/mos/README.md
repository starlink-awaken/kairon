# mos — Memory OS control plane

Unified memory control plane for eCOS (ADR-0372): **write** / **recall** / **status** / **forget** / **consolidate** / **knowledge-ref**.

- Envelope validation + intent routing
- Dual-track: raw (audit) + theta (searchable); theta failure does not erase raw
- Neo4j FACT path when `NEO4J_URI` is set; otherwise TemporalShadow (no hard Neo4j dep)
- Optional RBAC via `.omo/_truth/registry/memory-rbac.yaml` (`MOS_RBAC=1`)

```bash
cd projects/kairon
uv run --package mos pytest packages/mos/tests -q
uv run --package mos python -m mos status
```

Workspace entry points (prefer these over raw `python -m mos`):

- CLI: `cockpit memory {status,recall,write,forget,consolidate,knowledge-ref}`
- HTTP/UI: `/api/memory/*` · `/memory`
- BOS / Agora MCP: `bos://memory/mos/{write,recall,status,forget,consolidate,knowledge-ref}`

Env bootstrap: `source bin/memory-os-env.sh` · template `docs/operations/memory-os.env.example` · ops `.omo/standards/memory-os-ops.md`.
