# 命令参考

> 按用户旅程分组，涵盖所有 `workspace` 子命令。

---

## 🚪 进入 Workspace

### `workspace demo`

快速体验完整研究闭环：导入 → 形成研究对象 → 追问 → 发布 → 复盘。无副作用，适合新用户了解产品逻辑。

```bash
workspace demo
```

### `workspace help`

查看产品地图与所有命令概览。

```bash
workspace help
```

### `workspace profile [--edit]`

查看或编辑身份档案（L4 入口）。档案保存在 `~/.workspace/persona.yaml`。

| 参数 | 说明 |
|------|------|
| `--edit` | 用 `$EDITOR` 编辑身份档案 |

```bash
workspace profile          # 查看当前档案
workspace profile --edit   # 编辑身份档案
```

### `workspace status [--watch]`

工作台仪表盘 — 系统健康状态 + 活跃研究 + 推荐操作。

| 参数 | 说明 |
|------|------|
| `--watch` | 持续监控模式，自动刷新 |
| `--interval <秒>` | 刷新间隔（默认 5 秒） |

```bash
workspace status                    # 打开工作台
workspace status --watch            # 实时监控模式
workspace status --watch --interval 2  # 每 2 秒刷新
```

### `workspace daily [--days N]`

每日研究简报 — 回顾最近 N 天的研究活动。

| 参数 | 说明 |
|------|------|
| `--days N` | 回顾天数（默认 1） |

```bash
workspace daily          # 今日简报
workspace daily --days 7 # 过去 7 天
```

### `workspace dashboard`

打开 Web Dashboard。启动 Uvicorn 服务并在浏览器中打开。

```bash
workspace dashboard
```

---

## 🔬 研究 (research)

### 发起研究

#### `workspace research <topic>`

启动深度研究。依赖 `minerva` CLI，若未安装则提示降级。

```bash
workspace research "transformer architecture"
workspace research "2024 年 AI 趋势"
```

### 查看与管理

#### `workspace research --list [--limit N]`

按时间倒序列出研究记录。

| 参数 | 说明 |
|------|------|
| `--limit N` | 返回条数（默认 10） |

```bash
workspace research --list
workspace research --list --limit 20
```

#### `workspace research --open <ID>`

查看指定研究的全文、追问记录。

```bash
workspace research --open 1
workspace research --open 5
```

#### `workspace research --search <keyword>`

按关键词全文搜索（基于 FTS5）。

```bash
workspace research --search "transformer"
workspace research --search "attention" --limit 20
```

#### `workspace research --export markdown --open <ID>`

导出研究为 Markdown 或纯文本，保存到桌面。

| 参数 | 说明 |
|------|------|
| `--export FORMAT` | 导出格式（markdown / text），需配合 `--open` |

```bash
workspace research --export markdown --open 1
workspace research --export text --open 1
```

### 追问与深入

#### `workspace research --ask <ID> <question>`

对指定研究的追问。优先调用 minerva，降级到 ollama，最后使用本地缓存。

```bash
workspace research --ask 1 "为什么 Transformer 能取代 RNN?"
workspace research --ask 3 "最新的改进有哪些?"
```

### 追问工作流

#### `workspace research --follow-up`

列出所有活跃研究的追问状态，分组展示待追问/已回答/无追问项，并显示快捷操作建议。

```bash
workspace research --follow-up
```

---

### 发布

#### `workspace research --publish <ID> --style <style>`

发布研究为正式 Markdown 报告，保存到 `~/Desktop/workspace-published/`。

| 参数 | 说明 |
|------|------|
| `--style` | 输出风格：`brief`（一页简报）、`report`（完整报告）、`memo`（内部备忘） |

```bash
workspace research --publish 1 --style brief
workspace research --publish 3 --style report
workspace research --publish 5 --style memo
```

### 对比 & 合并 & 提炼

#### `workspace research --compare <ID> <ID> [...]`

并列对比多个研究。

```bash
workspace research --compare 1 2
workspace research --compare 1 3 5
```

#### `workspace research --merge <ID> <ID> [...]`

合并多个研究为新研究，自动建立 relation 关系。

```bash
workspace research --merge 1 2
```

#### `workspace research --digest <ID> <ID> [...]`

提炼多个研究为整合摘要，自动建立 relation 关系。

```bash
workspace research --digest 1 2
workspace research --digest 1 3 5
```

### 关系与时间线

#### `workspace research --dossier <ID>`

查看研究的完整档案：摘要、来源、标签、Agent、关系视图、发布产物。

```bash
workspace research --dossier 1
```

#### `workspace research --timeline <ID>`

查看研究的演化时间线：创建、派生、标注、发布、归档等所有事件。

```bash
workspace research --timeline 1
```

### 标签 & 重命名 & Agent

#### `workspace research --tag <ID> --labels <tag> [...]`

为研究添加或覆盖标签（自动去重、转小写）。

```bash
workspace research --tag 1 --labels llm agents
workspace research --tag 2 --labels "deep learning" nlp
```

#### `workspace research --rename <ID> --new-title <title>`

重命名研究标题。

```bash
workspace research --rename 1 --new-title "更好的标题"
```

#### `workspace research --agent <name>`

标记或查询处理 Agent。

```bash
workspace research --agent minerva           # 查询 Agent=minerva 的研究
workspace research --tag 1 --agent sophia    # 标记研究 1 的 Agent 为 sophia
```

### 归档 & 恢复

#### `workspace research --archive <ID> [...]`

将研究移入归档状态（从常规列表隐藏）。

```bash
workspace research --archive 4 5
```

#### `workspace research --unarchive <ID> [...]`

恢复已归档的研究。

```bash
workspace research --unarchive 4 5
```

### 隔离 & 恢复

#### `workspace research --quarantine <ID> [...]`

隔离可疑研究记录。

```bash
workspace research --quarantine 4 5
```

#### `workspace research --restore <ID> [...]`

恢复已隔离的研究。

```bash
workspace research --restore 4 5
```

### 审计 & 热力图

#### `workspace research --audit [--limit N]`

扫描可疑研究记录（空内容、traceback 等）。

```bash
workspace research --audit
workspace research --audit --limit 100
```

#### `workspace research --heatmap`

展示近 8 周的研究活跃度热力图。

```bash
workspace research --heatmap
```

### 健康报告

#### `workspace research --health`

展示活跃研究的半衰期衰减状态。按 Good（衰减 ≥ 0.7）、Fair（≥ 0.3）、Stale（< 0.3）分组，给出保鲜建议（追问可减慢衰减 20%，发布可提升 10%/次）。

```bash
workspace research --health
```

### 备份与恢复

#### `workspace research --backup [OUTPUT]`

全量备份所有研究数据（研究、关系、发布、事件）到 JSON 文件。默认保存到 `~/Desktop/workspace_backup.json`。

| 参数 | 说明 |
|------|------|
| `OUTPUT` | 可选，指定备份文件路径（默认桌面） |

```bash
workspace research --backup
workspace research --backup ~/Documents/research-backup-2026.json
```

#### `workspace research --backup-restore PATH`

从备份 JSON 文件恢复研究数据。自动跳过重复记录（按 topic + created_at 匹配），并重建 ID 映射关系。

```bash
workspace research --backup-restore ~/Desktop/workspace_backup.json
```

---

## 📥 导入

### `workspace import <source>`

从 URL 或本地文件导入内容，自动提取标题并保存为研究对象。

| 参数 | 说明 |
|------|------|
| `source` | URL（http/https）或本地文件路径 |

```bash
workspace import https://example.com/article
workspace import ~/Desktop/note.md
workspace import ~/Downloads/research.pdf
```

---

## 📐 契约 (contracts)

### `workspace contracts validate [path]`

验证契约。不传 path 时验证整个契约体系；传 path 时验证单个 WorkspaceObject JSON。

```bash
workspace contracts validate
workspace contracts validate ~/Desktop/my-object.json
```

### `workspace contracts list`

列出所有已注册的 Schema（包括 WorkspaceObject 和 eidos schemas）。

```bash
workspace contracts list
```

### `workspace contracts export-research <ID> [--output <path>]`

将研究对象导出为 WorkspaceObject JSON。

```bash
workspace contracts export-research 1
workspace contracts export-research 1 --output ~/Desktop/object.json
```

### `workspace contracts export identity [--output <path>]`

导出身份封套（IdentityEnvelope）。

```bash
workspace contracts export identity
workspace contracts export identity --output ~/Desktop/identity.json
```

### `workspace contracts export event --id <ID> [--output <path>]`

导出指定研究的事件封套（EventEnvelope）。

```bash
workspace contracts export event --id 1
workspace contracts export event --id 1 --output ~/Desktop/events.json
```

---

## 🏛️ 治理 (governance)

### `workspace governance <subcommand>`

委派到 arcnode-* 治理脚本。

| 子命令 | 说明 |
|--------|------|
| `calibrate` | 校准 |
| `rechain` | 重新链接 |
| `evolve` | 演化 |
| `report` | 报告 |
| `drift-check` | 漂移检查 |
| `validate` | 验证 |

```bash
workspace governance calibrate --check
workspace governance rechain
workspace governance report
```

---

## 🩺 其他

### `workspace product-health`

运行产品健康度检测。

```bash
workspace product-health
```

---

## 🚀 快速开始

### `workspace quickstart [--fix] [--model MODEL]`

新用户快速上手向导，包含 4 步：环境核验 → 推荐配置 → 上手指引 → 下一步。

| 参数 | 说明 |
|------|------|
| `--fix` | 自动检测并修复常见问题（ollama 安装/启动/模型拉取、数据库初始化） |
| `--model` | 默认拉取的 LLM 模型名（默认 `llama3.2`） |

```bash
workspace quickstart                    # 交互式向导
workspace quickstart --fix              # 自动修复模式
workspace quickstart --fix --model qwen3.5:4b  # 指定模型
```

### `workspace init [--fix] [--model MODEL]`

初始化向导，与 `quickstart` 完全一致。

```bash
workspace init --fix
```

---

## 🔌 MCP 服务

### `workspace mcp [--transport stdio|sse] [--port PORT] [--list-tools]`

启动 Workspace MCP server 或列出已注册的工具。

| 参数 | 说明 |
|------|------|
| `--transport` | 传输协议：`stdio`（默认，与 MCP 客户端通信）或 `sse`（HTTP SSE） |
| `--port` | SSE 模式监听端口（默认 7431） |
| `--list-tools` | 列出已注册的 MCP 工具，不启动 server |

```bash
workspace mcp                           # stdio 模式
workspace mcp --transport sse            # SSE 模式
workspace mcp --transport sse --port 8000  # 自定义端口
workspace mcp --list-tools               # 列出工具
```
