# eu-pricing — EU (Energy Unit) Virtual Resource Accounting

L2 能力层：虚拟资源记账系统，管理 Pipeline 操作的能量单元消耗。

## CLI

```bash
eu-pricing balance [caller]     # 查询 EU 余额
eu-pricing consume [caller] [op] # 消费 EU
eu-pricing pricing              # 显示定价表
eu-pricing --json               # JSON 输出
```

## 集成

通过 Agora MCP 与 SharedBrain D-Economy 通信，控制 Pipeline 操作的成本。
