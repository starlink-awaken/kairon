# CLAUDE.md — kairon

> 知识工程与研究栈 · 16 个 live installable Python packages
> 根工作区文档：`../CLAUDE.md`、`../AGENTS.md`、`../LAYER-INDEX.md`
> 当前 live inventory、架构和边界以 `docs/live_inventory.md`、`docs/architecture_audit.md`、`docs/cross_project_boundary_audit.md` 为准

## 启动前提

1. 先读根工作区 `../CLAUDE.md`
2. 把 `packages/*/pyproject.toml` 视为唯一 live package truth source
3. 不要把 Agora route alias、旧 phase 文档、历史迁移叙事当成当前仓库拓扑事实

## 当前仓库定位

`kairon` 现在主要是 **L2 知识引擎仓库**，不是旧阶段里那个同时承载 runtime、gateway、bridge、SSOT 的大一统 monorepo。

当前 live package 只剩 16 个，分成三层：

### 基础与共用 primitives

- `core-models`
- `health-profile`
- `kairon-lib-events`
- `kairon-observability`
- `kairon-pipeline`
- `kairon-plugin-sdk`
- `kairon-utils`

### 知识与研究引擎

- `codeanalyze`
- `eidos`
- `iris`
- `kos`
- `kronos`
- `minerva`
- `ontoderive`
- `sophia`

### 对外能力面

- `forge`

## 重要边界

- `aetherforge` 已是独立 sibling project，LLM gateway 正在往它收敛
- `agora` route/service registry 里仍有 `sharedbrain-bridge`、`sot-bridge`、`engine-core`、`protocols-layer`、`ssot` 等历史别名
- 这些名字 **不是** 当前 `kairon` live installable package
- `SharedBrain` 现在更接近历史概念边界或外部数据边界，而不是当前 `kairon` 仓内 live package surface

## 工作约束

- 改架构、inventory、boundary 相关内容时，优先同步这些文件：
  - `AGENTS.md`
  - `docs/live_inventory.md`
  - `docs/architecture_audit.md`
  - `docs/cross_project_boundary_audit.md`
  - `docs/agora_route_drift_audit.md`
- 不要重新引入已经删掉的 workspace 成员声明
- 不要把 compatibility alias 写成 live capability

## 常用命令

```bash
uv sync
make test
make test-fast
make lint
make format
make typecheck  # mypy strict 试点
```

## 当前已知事实

- `pyproject.toml` 的 `requires-python` 是 `>=3.10` (各包的 ruff 配置 target-version 为 py313)
- Ruff target 仍是 `py313`
- `tool.uv.workspace.members = ["packages/*"]`
- 已删掉的旧包残留不应再出现在 workspace source/exclude 中

## 验证口径

- package count：直接扫 `packages/*/pyproject.toml`
- route truth：同时看 `src/agora-routes.json` 和 `src/agora/l0_registry_overrides.yaml`
- service truth：看 `src/agora-services.json`，但要区分 live target 和 compatibility alias
