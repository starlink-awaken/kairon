# AGENTS.md — kairon

    > Scope: project-local developer guide for `kairon`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L2
    - Stack: Python / uv workspace / pytest
    - Responsibility: 知识工程与研究引擎 monorepo

    Do not copy volatile facts such as test counts, tool counts, service counts, ports, or current health into this file.

    ## Before Editing

    1. Read this file and [`CLAUDE.md`](CLAUDE.md) when it exists.
    2. Check `git status --short` inside this project and at the workspace root.
    3. Read the specific source or tests you are about to change.
    4. Prefer project-local commands and targeted tests.

    ## Commands

    ```bash
    uv sync
make test-diff
make lint
    ```

    ## Key Files

    - `pyproject.toml`
- `packages/`
- `packages/kos/`
- `packages/eidos/`
- `packages/minerva/`
- `packages/ontoderive/`

    ## Gotchas

    - `包清单和数量以 ../../docs/project-registry.yaml 与 pyproject.toml 为准。`
- 修改单包优先 make test-diff，跨包契约变更再扩大测试。
- 不要把派生日志或运行快照写进长期说明文档。

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
