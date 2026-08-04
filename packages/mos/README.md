# mos — Memory OS control plane

Unified memory **write** / **recall** / **status** for eCOS (ADR-0372).

- Envelope validation + intent routing
- Dual-track: raw (audit) + theta (searchable); theta failure does not erase raw
- Injectable backends for tests; optional live KOS/gbrain later

```bash
cd projects/kairon
uv run --package mos pytest packages/mos/tests -q
uv run --package mos python -m mos status
```

BOS (when registered): `bos://memory/mos/{write,recall,status}`.
