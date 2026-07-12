# kairon — Architecture

> **Layer**: L2 引擎面  
> **Role**: 知识工程与研究引擎 / 19+ packages monorepo  
> **Stack**: Python 3.13+, uv workspace, pytest  
> **Health**: See local CI and package-level verification
> **SSOT**: 运行时健康、测试规模、包数量以本项目 CI、本地测试命令和 workspace governance SSOT 为准
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 内部架构

```mermaid

graph TB
    Agora[agora I0]
    subgraph Kairon["kairon packages/"]
        KOS[kos]
        MIN[minerva]
        EID[eidos]
        KRO[kronos]
        ONT[ontoderive]
        CA[codeanalyze]
        IRIS[iris]
        FORGE[forge]
    end
    GBR[gbrain]
    ECOS[ecos MOF]

    Agora -->|bos://memory/*| KOS
    Agora -->|bos://analysis/*| MIN
    Agora -->|bos://analysis/*| ONT
    Agora -->|bos://analysis/*| CA
    Agora -->|bos://capability/*| FORGE
    KOS --> GBR
    MIN --> ONT
    KRO --> GBR
    EID --> ECOS

```

## 2. 入口

| Type | Entry | Port / Notes |
|:--|:--|:--|
| CLI | `per-package (kos, kronos, minerva, ...)` |  |
| BOS | `bos://memory/*, bos://analysis/*, bos://persona/*` |  |

## 3. 核心模块

| Module | Responsibility |
|:--|:--|
| `packages/kos/` | 跨域语义搜索 / KOS 知识图谱 |
| `packages/minerva/` | 深度研究引擎 |
| `packages/eidos/` | 认知记忆系统 (memory/nks/continuity/CRDT/learning + schema) — **kairon 枢纽**, 39K LOC, 被最多外部包依赖 |
| `packages/kronos/` | 知识摄取管线 |
| `packages/ontoderive/` | 本体推导与推理 |
| `packages/codeanalyze/` | AST 代码分析 |
| `packages/forge/` | Agent/工具集市 |
| `packages/iris/` | 发现与召回 |

## 4. 测试

```bash
cd projects/kairon && make test-diff  # or make test
```

## 架构概览

参见工作区架构概览图：[`../../docs/ARCHITECTURE-DIAGRAM.md`](../../docs/ARCHITECTURE-DIAGRAM.md)
