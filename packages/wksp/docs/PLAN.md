# Phase 2: Dashboard 工作台化

## 目标
将 `workspace status` 从静态健康看板 → 交互式工作台

## 改动
1. `_render_status_snapshot` → `_render_workbench` 重写
2. 顶部：快捷行动栏（一键操作）
3. 中部：今日工作台（活跃研究 + 可继续）
4. 底部：系统状态（压缩点状指示 + 异常展开）
5. 结尾：上下文感知推荐

## 不变
- `--watch` / `--interval` 实时监控模式保持
- 所有现有功能不删除
