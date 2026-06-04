"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Bill Generator ≡ Generator
# 内涵 ≝ {Bill, Generator}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, BillGenerator)}
# 功能 ⊢ {Bill_Generator, Init_Bill, Validate_Generator}
# =============================================================================

"""---
Type: BillGenerator
Layer: L3
Domain: D-Cloud
Status: ACTIVE
Updated: "2026-03-31"
Authority: 2
Compiled-From: []
Keywords: [billing, invoice, generation, storage]
---"""
"""账单生成器

生成账单报告和发票，管理账单存储
"""

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from kaironcloud_billing.models import (
    Bill,
    BillDetails,
    BillLineItem,
    BillStatus,
    TenantSubscription,
    TierType,
    UsageReport,
)
from kaironcloud_billing.pricing import PricingModel
from kaironcloud_billing.usage_tracker import UsageTracker


class BillGenerator:
    """账单生成器"""

    def __init__(self, db_path: str, usage_tracker: UsageTracker | None = None) -> None:
        """初始化账单生成器

        Args:
            db_path: 账单数据库路径
            usage_tracker: 使用量追踪器（可选）
        """
        self.db_path = db_path
        self.usage_tracker = usage_tracker
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    bill_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    base_cost TEXT NOT NULL,
                    overage_cost TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    status TEXT NOT NULL,
                    line_items TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    paid_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_subscriptions (
                    tenant_id TEXT PRIMARY KEY,
                    tier TEXT NOT NULL,
                    billing_day INTEGER DEFAULT 1,
                    auto_renew INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active',
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    async def update_tenant_subscription(
        self, tenant_id: str, tier: TierType, billing_day: int = 1, auto_renew: bool = True
    ) -> TenantSubscription:
        """更新租户订阅套餐

        Args:
            tenant_id: 租户ID
            tier: 套餐类型
            billing_day: 账单日
            auto_renew: 是否自动续费

        Returns:
            订阅对象
        """
        now = datetime.now(UTC)

        with sqlite3.connect(self.db_path) as conn:
            # 检查是否已存在
            cursor = conn.execute("SELECT started_at FROM tenant_subscriptions WHERE tenant_id = ?", (tenant_id,))
            row = cursor.fetchone()
            started_at = row[0] if row else now.isoformat()

            conn.execute(
                """INSERT OR REPLACE INTO tenant_subscriptions
                   (tenant_id, tier, billing_day, auto_renew, status, started_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tenant_id, tier.value, billing_day, 1 if auto_renew else 0, "active", started_at, now.isoformat()),
            )
            conn.commit()

        return TenantSubscription(
            tenant_id=tenant_id,
            tier=tier.value,
            started_at=datetime.fromisoformat(started_at),
            billing_day=billing_day,
            auto_renew=auto_renew,
            status="active",
        )

    async def get_tenant_subscription(self, tenant_id: str) -> TenantSubscription | None:
        """获取租户订阅信息

        Args:
            tenant_id: 租户ID

        Returns:
            订阅对象，不存在返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT tenant_id, tier, billing_day, auto_renew, status, started_at
                   FROM tenant_subscriptions WHERE tenant_id = ?""",
                (tenant_id,),
            )
            row = cursor.fetchone()
            if row:
                return TenantSubscription(
                    tenant_id=row[0],
                    tier=row[1],
                    billing_day=row[2],
                    auto_renew=bool(row[3]),
                    status=row[4],
                    started_at=datetime.fromisoformat(row[5]),
                )
            return None

    def _get_tenant_tier(self, tenant_id: str) -> TierType:
        """获取租户当前套餐"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT tier FROM tenant_subscriptions WHERE tenant_id = ?", (tenant_id,))
            row = cursor.fetchone()
            if row:
                return TierType(row[0])
            return TierType.FREE

    async def generate_monthly_bill(self, tenant_id: str, year: int, month: int, tier: str | None = None) -> Bill:
        """生成月度账单"""
        if self.usage_tracker is None:
            raise ValueError("UsageTracker is required to generate bills")

        period_start = datetime(year, month, 1)
        if month == 12:
            period_end = datetime(year + 1, 1, 1)
        else:
            period_end = datetime(year, month + 1, 1)

        # 获取租户套餐
        if tier is None:
            tier = self._get_tenant_tier(tenant_id).value

        # 获取使用报告
        usage_report = await self.usage_tracker.get_usage_report(tenant_id, period_start, period_end)

        # 计算账单
        bill = PricingModel.calculate_cost(tier, usage_report)
        self._save_bill(bill)

        return bill

    def _save_bill(self, bill: Bill) -> None:
        """保存账单到数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO bills
                   (bill_id, tenant_id, tier, period_start, period_end,
                    base_cost, overage_cost, total_cost, status, line_items,
                    created_at, paid_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    bill.bill_id,
                    bill.tenant_id,
                    bill.tier,
                    bill.period_start.isoformat(),
                    bill.period_end.isoformat(),
                    str(bill.base_cost),
                    str(bill.overage_cost),
                    str(bill.total_cost),
                    bill.status.value,
                    json.dumps(
                        [
                            {
                                "description": item.description,
                                "quantity": item.quantity,
                                "unit_price": str(item.unit_price),
                                "amount": str(item.amount),
                                "resource_type": item.resource_type,
                            }
                            for item in bill.line_items
                        ]
                    ),
                    bill.created_at.isoformat(),
                    bill.paid_at.isoformat() if bill.paid_at else None,
                ),
            )
            conn.commit()

    def _row_to_bill(self, row: Sequence[object]) -> Bill:
        """数据库行转换为账单对象"""
        line_items_data = json.loads(row[9])
        line_items = [
            BillLineItem(
                description=item["description"],
                quantity=item["quantity"],
                unit_price=Decimal(item["unit_price"]),
                amount=Decimal(item["amount"]),
                resource_type=item.get("resource_type"),
            )
            for item in line_items_data
        ]

        return Bill(
            bill_id=row[0],
            tenant_id=row[1],
            tier=row[2],
            period_start=datetime.fromisoformat(row[3]),
            period_end=datetime.fromisoformat(row[4]),
            base_cost=Decimal(row[5]),
            overage_cost=Decimal(row[6]),
            total_cost=Decimal(row[7]),
            status=BillStatus(row[8]),
            line_items=line_items,
            created_at=datetime.fromisoformat(row[10]),
            paid_at=datetime.fromisoformat(row[11]) if row[11] else None,
        )

    async def get_bill(self, bill_id: str) -> Bill | None:
        """获取账单"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM bills WHERE bill_id = ?", (bill_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_bill(row)
            return None

    async def get_bill_details(self, bill_id: str) -> BillDetails | None:
        """获取账单详情"""
        if self.usage_tracker is None:
            raise ValueError("UsageTracker is required to get bill details")

        bill = await self.get_bill(bill_id)
        if not bill:
            return None

        summary = await self.usage_tracker.get_usage_summary(bill.tenant_id, bill.period_start, bill.period_end)

        usage_report = UsageReport(
            tenant_id=bill.tenant_id,
            period_start=bill.period_start,
            period_end=bill.period_end,
            compute_hours=summary["compute_hours"],
            storage_gb=summary["storage_gb"],
            api_calls=summary["api_calls"],
            breakdown=[],
        )

        tier_info = PricingModel.get_tier_config(TierType(bill.tier))

        return BillDetails(bill=bill, usage_report=usage_report, tier_info=tier_info)

    async def export_bill_pdf(self, bill_id: str) -> bytes:
        """导出账单为PDF格式

        简化实现：返回包含账单信息的文本字节
        """
        bill = await self.get_bill(bill_id)
        if not bill:
            raise ValueError(f"Bill not found: {bill_id}")

        # 简化PDF生成：返回文本内容
        content = f"""B-OS Cloud Invoice
====================

Bill ID: {bill.bill_id}
Tenant ID: {bill.tenant_id}
Tier: {bill.tier}
Period: {bill.period_start.strftime("%Y-%m-%d")} to {bill.period_end.strftime("%Y-%m-%d")}
Status: {bill.status.value}

Line Items:
"""
        for item in bill.line_items:
            content += f"- {item.description}: ${item.amount}\n"

        content += f"""
Base Cost: ${bill.base_cost}
Overage Cost: ${bill.overage_cost}
Total: ${bill.total_cost}

Generated at: {datetime.now(UTC).isoformat()}
"""
        return content.encode("utf-8")

    async def mark_bill_paid(self, bill_id: str) -> Bill:
        """标记账单为已支付"""
        bill = await self.get_bill(bill_id)
        if not bill:
            raise ValueError(f"Bill not found: {bill_id}")

        bill.status = BillStatus.PAID
        bill.paid_at = datetime.now(UTC)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE bills SET status = ?, paid_at = ? WHERE bill_id = ?",
                (BillStatus.PAID.value, bill.paid_at.isoformat(), bill_id),
            )
            conn.commit()

        return bill

    def close(self) -> None:
        """关闭资源"""
        pass
