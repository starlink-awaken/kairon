# kairon

    > L2 · 知识工程与研究引擎 monorepo
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    知识工程与研究引擎 monorepo.

    ## Quick Start

    ```bash
    uv sync
make test-diff
make lint
    ```

    ## Key Surfaces

    - `pyproject.toml`
- `packages/`
- `packages/kos/`
- `packages/eidos/`
- `packages/minerva/`
- `packages/ontoderive/`

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
