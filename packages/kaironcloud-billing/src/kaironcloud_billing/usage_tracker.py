"""使用量追踪器

追踪租户资源使用量，支持计算时间、存储、API调用等多种资源类型
"""

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from .models import ResourceType, UsageRecord, UsageReport


class UsageTracker:
    """追踪租户资源使用量

    提供异步接口追踪各类资源使用情况，支持数据持久化到SQLite

    Attributes:
        db_path: 数据库文件路径
        _conn: 数据库连接
    """

    def __init__(self, db_path: str | None = None) -> None:
        """初始化使用量追踪器

        Args:
            db_path: 数据库文件路径，默认使用 data/db/billing_usage.db
        """
        if db_path is None:
            db_path = "data/db/billing_usage.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self) -> None:
        """初始化数据库表"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_records (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                worker_type TEXT,
                storage_type TEXT,
                endpoint TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_timestamp
            ON usage_records(tenant_id, timestamp)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_resource_type
            ON usage_records(resource_type)
        """)

        conn.commit()

    async def track_compute_time(
        self,
        tenant_id: str,
        duration_ms: int,
        worker_type: str = "default",
        timestamp: datetime | None = None,
    ) -> UsageRecord:
        """追踪计算时间

        Args:
            tenant_id: 租户ID
            duration_ms: 计算时长（毫秒）
            worker_type: 工作器类型
            timestamp: 记录时间，默认使用当前UTC时间

        Returns:
            创建的使用记录
        """
        hours = duration_ms / (1000 * 60 * 60)

        record = UsageRecord(
            tenant_id=tenant_id,
            resource_type=ResourceType.COMPUTE,
            quantity=hours,
            unit="hours",
            timestamp=timestamp or datetime.now(UTC),
            metadata={"worker_type": worker_type, "duration_ms": duration_ms},
        )

        self._save_record(record, worker_type=worker_type)
        return record

    async def track_storage(
        self,
        tenant_id: str,
        bytes_used: int,
        storage_type: str = "standard",
        timestamp: datetime | None = None,
    ) -> UsageRecord:
        """追踪存储使用

        Args:
            tenant_id: 租户ID
            bytes_used: 使用的字节数
            storage_type: 存储类型
            timestamp: 记录时间，默认使用当前UTC时间

        Returns:
            创建的使用记录
        """
        gb = bytes_used / (1024 * 1024 * 1024)

        record = UsageRecord(
            tenant_id=tenant_id,
            resource_type=ResourceType.STORAGE,
            quantity=gb,
            unit="gb",
            timestamp=timestamp or datetime.now(UTC),
            metadata={"storage_type": storage_type, "bytes_used": bytes_used},
        )

        self._save_record(record, storage_type=storage_type)
        return record

    async def track_api_calls(
        self,
        tenant_id: str,
        endpoint: str,
        count: int = 1,
        timestamp: datetime | None = None,
    ) -> UsageRecord:
        """追踪API调用

        Args:
            tenant_id: 租户ID
            endpoint: API端点
            count: 调用次数
            timestamp: 记录时间，默认使用当前UTC时间

        Returns:
            创建的使用记录
        """
        record = UsageRecord(
            tenant_id=tenant_id,
            resource_type=ResourceType.API,
            quantity=float(count),
            unit="calls",
            timestamp=timestamp or datetime.now(UTC),
            metadata={"endpoint": endpoint, "count": count},
        )

        self._save_record(record, endpoint=endpoint)
        return record

    def _save_record(
        self,
        record: UsageRecord,
        worker_type: str | None = None,
        storage_type: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """保存记录到数据库"""
        conn = self._get_conn()
        record_id = str(uuid.uuid4())

        conn.execute(
            """
            INSERT INTO usage_records
            (id, tenant_id, resource_type, quantity, unit, timestamp, metadata, worker_type, storage_type, endpoint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                record.tenant_id,
                record.resource_type,
                record.quantity,
                record.unit,
                record.timestamp.isoformat(),
                json.dumps(record.metadata),
                worker_type,
                storage_type,
                endpoint,
            ),
        )
        conn.commit()

    async def get_usage_report(self, tenant_id: str, start_date: datetime, end_date: datetime) -> UsageReport:
        """获取使用报告

        汇总指定时间段内的资源使用情况

        Args:
            tenant_id: 租户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            使用报告
        """
        conn = self._get_conn()

        cursor = conn.execute(
            """
            SELECT * FROM usage_records
            WHERE tenant_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
            """,
            (tenant_id, start_date.isoformat(), end_date.isoformat()),
        )

        rows = cursor.fetchall()

        compute_hours = 0.0
        storage_gb = 0.0
        api_calls = 0
        breakdown = []

        for row in rows:
            record = UsageRecord(
                tenant_id=row["tenant_id"],
                resource_type=row["resource_type"],
                quantity=row["quantity"],
                unit=row["unit"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"] or "{}"),
            )
            breakdown.append(record)

            if record.resource_type == ResourceType.COMPUTE:
                compute_hours += record.quantity
            elif record.resource_type == ResourceType.STORAGE:
                storage_gb += record.quantity
            elif record.resource_type == ResourceType.API:
                api_calls += int(record.quantity)

        return UsageReport(
            tenant_id=tenant_id,
            period_start=start_date,
            period_end=end_date,
            compute_hours=compute_hours,
            storage_gb=storage_gb,
            api_calls=api_calls,
            breakdown=breakdown,
        )

    async def get_usage_summary(
        self,
        tenant_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        days: int | None = None,
    ) -> dict[str, Any]:
        """获取使用摘要

        Args:
            tenant_id: 租户ID
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            days: 统计天数（与start_date/end_date互斥，默认30）

        Returns:
            使用摘要字典
        """
        if days is not None:
            end_date_resolved = datetime.now(UTC)
            start_date_resolved = end_date_resolved - timedelta(days=days)
        else:
            if end_date is None:
                end_date_resolved = datetime.now(UTC)
            else:
                end_date_resolved = end_date
            if start_date is None:
                start_date_resolved = end_date_resolved - timedelta(days=30)
            else:
                start_date_resolved = start_date

        report = await self.get_usage_report(tenant_id, start_date_resolved, end_date_resolved)

        period_days = (end_date_resolved - start_date_resolved).days

        return {
            "tenant_id": tenant_id,
            "period_days": period_days,
            "compute_hours": round(report.compute_hours, 2),
            "storage_gb": round(report.storage_gb, 2),
            "api_calls": report.api_calls,
            "total_records": len(report.breakdown),
        }

    async def get_tenant_usage_by_resource(
        self, tenant_id: str, resource_type: str, days: int = 30
    ) -> list[UsageRecord]:
        """获取特定资源类型的使用记录

        Args:
            tenant_id: 租户ID
            resource_type: 资源类型
            days: 统计天数

        Returns:
            使用记录列表
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        conn = self._get_conn()
        cursor = conn.execute(
            """
            SELECT * FROM usage_records
            WHERE tenant_id = ? AND resource_type = ?
            AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp DESC
            """,
            (tenant_id, resource_type, start_date.isoformat(), end_date.isoformat()),
        )

        records = []
        for row in cursor.fetchall():
            records.append(
                UsageRecord(
                    tenant_id=row["tenant_id"],
                    resource_type=row["resource_type"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    metadata=json.loads(row["metadata"] or "{}"),
                )
            )

        return records

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口"""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """异步上下文管理器退出"""
        self.close()
        return False
