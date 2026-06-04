"""计费系统数据模型

定义使用量记录、账单、使用报告等核心数据结构
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ResourceType(StrEnum):
    """资源类型"""

    COMPUTE = "compute"
    STORAGE = "storage"
    API = "api"


class BillStatus(StrEnum):
    """账单状态"""

    DRAFT = "draft"
    PENDING = "pending"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TierType(StrEnum):
    """套餐类型"""

    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class UsageRecord:
    """使用量记录

    记录单次资源使用详情

    Attributes:
        tenant_id: 租户ID
        resource_type: 资源类型 (compute/storage/api)
        quantity: 使用数量
        unit: 单位 (hours/gb/calls)
        timestamp: 记录时间
        metadata: 额外元数据
    """

    tenant_id: str
    resource_type: str
    quantity: float
    unit: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class UsageBreakdown:
    """使用量明细"""

    resource_type: str
    quantity: float
    unit: str
    cost: Decimal


@dataclass
class UsageReport:
    """使用报告

    汇总指定时间段内的资源使用情况

    Attributes:
        tenant_id: 租户ID
        period_start: 报告开始时间
        period_end: 报告结束时间
        compute_hours: 计算小时数
        storage_gb: 存储使用量(GB)
        api_calls: API调用次数
        breakdown: 详细使用记录列表
    """

    tenant_id: str
    period_start: datetime
    period_end: datetime
    compute_hours: float = 0.0
    storage_gb: float = 0.0
    api_calls: int = 0
    breakdown: list[UsageRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.period_start, str):
            self.period_start = datetime.fromisoformat(self.period_start)
        if isinstance(self.period_end, str):
            self.period_end = datetime.fromisoformat(self.period_end)


@dataclass
class BillLineItem:
    """账单行项目"""

    description: str
    quantity: float
    unit_price: Decimal
    amount: Decimal
    resource_type: str | None = None


@dataclass
class Bill:
    """账单

    月度账单实体

    Attributes:
        bill_id: 账单ID
        tenant_id: 租户ID
        tier: 套餐类型
        period_start: 计费周期开始
        period_end: 计费周期结束
        base_cost: 基础套餐费用
        overage_cost: 超额费用
        total_cost: 总费用
        status: 账单状态
        line_items: 账单明细行
        created_at: 创建时间
        paid_at: 支付时间
    """

    bill_id: str
    tenant_id: str
    tier: str
    period_start: datetime
    period_end: datetime
    base_cost: Decimal = Decimal("0")
    overage_cost: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    status: str = BillStatus.DRAFT  # type: ignore[assignment]
    line_items: list[BillLineItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    paid_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.period_start, str):
            self.period_start = datetime.fromisoformat(self.period_start)
        if isinstance(self.period_end, str):
            self.period_end = datetime.fromisoformat(self.period_end)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.paid_at, str):
            self.paid_at = datetime.fromisoformat(self.paid_at)
        self.base_cost = Decimal(str(self.base_cost))
        self.overage_cost = Decimal(str(self.overage_cost))
        self.total_cost = Decimal(str(self.total_cost))


@dataclass
class BillDetails:
    """账单详情"""

    bill: Bill
    usage_report: UsageReport
    tier_info: dict[str, Any]


@dataclass
class PricingTier:
    """定价套餐"""

    name: str
    monthly_cost: Decimal
    included_compute_hours: float
    included_storage_gb: float
    included_api_calls: int
    overage_compute_per_hour: Decimal
    overage_storage_per_gb: Decimal
    overage_api_per_1000: Decimal


@dataclass
class TenantSubscription:
    """租户订阅信息"""

    tenant_id: str
    tier: str
    started_at: datetime
    billing_day: int = 1
    auto_renew: bool = True
    status: str = "active"
