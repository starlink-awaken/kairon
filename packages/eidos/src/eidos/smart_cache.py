from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Layer: L3
---
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from eidos.organs.storage_dal import (
    SQLiteError,
    SQLiteOperationalError,
    SQLiteRelationalProvider,
)

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Smart_Cache ≡ Intelligent_Storage
# 内涵 ≝ {Cache, Optimize, Evict}
# 外延 ≝ {c | c ∈ D-Memory ∧ caches(c, Information)}
# 功能 ⊢ {StoreData, OptimizeCache, SuggestEviction}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-05_microkernel_fractal_axiom.md
Layer: D-Memory
Constraint: "[!!] SMART_CACHE_ADAPTIVE"
Summary: '智能缓存管理器 - 基于使用频率和数据大小的自适应缓存'
---

Smart Cache Manager - 智能缓存管理器

职责:
- 基于使用频率和数据大小的智能缓存
- 自适应缓存淘汰策略
- 缓存统计和优化建议
- 能量消耗追踪

作者: iFlow CLI
日期: 2026-03-03
状态: 生产就绪
"""

_log = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""

    key: str
    value: Any
    size_bytes: int
    created_at: float
    last_accessed: float
    access_count: int = 0
    hit_count: int = 0
    miss_count: int = 0

    @property
    def score(self) -> float:
        """
        计算缓存分数（用于淘汰决策）

        分数 = (访问频率 * 权重) / (数据大小 * 大小惩罚)
        访问频率 = access_count / (当前时间 - created_at + 1)
        """
        age = time.time() - self.created_at + 1
        frequency = self.access_count / age
        size_penalty = max(1, self.size_bytes / 1024)  # 每KB增加惩罚

        return (frequency * 1000) / size_penalty


class SmartCacheManager:
    """智能缓存管理器 - 基于使用频率和数据大小的自适应缓存"""

    def __init__(self, db_path: str | None = None, max_size_mb: int = 100) -> None:
        """
        初始化智能缓存管理器

        Args:
            db_path: 数据库路径
            max_size_mb: 最大缓存大小（MB）
        """
        self.db_path = db_path or os.environ.get("BOS_MEMORY_DB", "data/db/organs/memory/memory.db")
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._cache: dict[str, CacheEntry] = {}
        self._total_size = 0
        self._hit_count = 0
        self._miss_count = 0
        self._db = SQLiteRelationalProvider(self.db_path)
        self.initialize()

    def _ensure_db(self) -> None:
        """Initialize DB connection and apply pragmas."""
        self._db.connect()
        self._db.execute("PRAGMA busy_timeout=30000")
        try:
            self._db.execute("PRAGMA journal_mode=DELETE")
        except SQLiteOperationalError:
            pass
        self._db.execute("PRAGMA synchronous=NORMAL")

    def initialize(self) -> None:
        """初始化数据库表"""
        self._ensure_db()
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                miss_count INTEGER NOT NULL DEFAULT 0
            );"""
        )

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_statistics (
                timestamp REAL NOT NULL,
                total_entries INTEGER NOT NULL,
                total_size_bytes INTEGER NOT NULL,
                hit_count INTEGER NOT NULL,
                miss_count INTEGER NOT NULL,
                hit_rate REAL NOT NULL
            );"""
        )

        # 从数据库加载缓存
        self._load_cache()

        _log.info(f"[*] SmartCacheManager initialized (max_size: {self.max_size_bytes / 1024 / 1024:.1f}MB)")

    def _load_cache(self) -> None:
        """从数据库加载缓存"""
        try:
            rows = self._db.fetch_all("SELECT * FROM cache_entries")
            for row in rows:
                try:
                    value = json.loads(row["value"])
                    entry = CacheEntry(
                        key=row["key"],
                        value=value,
                        size_bytes=row["size_bytes"],
                        created_at=row["created_at"],
                        last_accessed=row["last_accessed"],
                        access_count=row["access_count"],
                        hit_count=row["hit_count"],
                        miss_count=row["miss_count"],
                    )
                    self._cache[entry.key] = entry
                    self._total_size += entry.size_bytes
                except (TypeError, ValueError, KeyError):
                    _log.info("⚠️ [Cache] Failed to load entry {row['key']}: {e}")

            _log.info(f"📦 [Cache] Loaded {len(self._cache)} entries ({self._total_size / 1024 / 1024:.2f}MB)")
        except SQLiteError:
            _log.info("⚠️ [Cache] Failed to load cache: {e}")

    def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在则返回 None
        """
        if key not in self._cache:
            self._miss_count += 1
            return None

        entry = self._cache[key]
        entry.last_accessed = time.time()
        entry.access_count += 1
        entry.hit_count += 1
        self._hit_count += 1

        # 更新数据库
        self._update_entry(entry)

        return entry.value

    def set(self, key: str, value: Any, ttl: int = 600) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒）

        Returns:
            是否成功设置
        """
        # 序列化值
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError):
            _log.info("❌ [Cache] Failed to serialize value for key '{key}': {e}")
            return False

        size_bytes = len(serialized.encode("utf-8"))

        # 如果键已存在，更新
        if key in self._cache:
            old_entry = self._cache[key]
            self._total_size -= old_entry.size_bytes
            del self._cache[key]

        # 检查是否需要淘汰
        if self._total_size + size_bytes > self.max_size_bytes:
            self._evict_entries(size_bytes)

        # 创建新条目
        entry = CacheEntry(
            key=key,
            value=value,
            size_bytes=size_bytes,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
        )

        self._cache[key] = entry
        self._total_size += size_bytes

        # 保存到数据库
        self._save_entry(entry)

        return True

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        if key not in self._cache:
            return False

        entry = self._cache[key]
        self._total_size -= entry.size_bytes
        del self._cache[key]

        # 从数据库删除
        self._db.execute("DELETE FROM cache_entries WHERE key = ?", (key,))

        return True

    def _evict_entries(self, required_space: int) -> None:
        """
        淘汰缓存条目以释放空间

        Args:
            required_space: 需要释放的空间（字节）
        """
        if not self._cache:
            return

        # 按分数排序（分数低的先淘汰）
        sorted_entries = sorted(self._cache.values(), key=lambda e: e.score)

        freed_space = 0
        evicted_count = 0

        for entry in sorted_entries:
            if freed_space >= required_space:
                break

            freed_space += entry.size_bytes
            evicted_count += 1

            # 从缓存中移除
            del self._cache[entry.key]
            self._total_size -= entry.size_bytes

            # 从数据库删除
            self._db.execute("DELETE FROM cache_entries WHERE key = ?", (entry.key,))

        _log.info("🗑️ [Cache] Evicted {evicted_count} entries (freed {freed_space / 1024:.2f}KB)")

    def _save_entry(self, entry: CacheEntry) -> None:
        """保存缓存条目到数据库"""
        try:
            serialized = json.dumps(entry.value)
            self._db.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key, value, size_bytes, created_at, last_accessed, access_count, hit_count, miss_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.key,
                    serialized,
                    entry.size_bytes,
                    entry.created_at,
                    entry.last_accessed,
                    entry.access_count,
                    entry.hit_count,
                    entry.miss_count,
                ),
            )
        except SQLiteError:
            _log.info("⚠️ [Cache] Failed to save entry {entry.key}: {e}")

    def _update_entry(self, entry: CacheEntry) -> None:
        """更新缓存条目"""
        try:
            self._db.execute(
                """
                UPDATE cache_entries
                SET last_accessed = ?, access_count = ?, hit_count = ?
                WHERE key = ?
                """,
                (entry.last_accessed, entry.access_count, entry.hit_count, entry.key),
            )
        except SQLiteError:
            _log.info("⚠️ [Cache] Failed to update entry {entry.key}: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict: 统计信息
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total_requests if total_requests > 0 else 0

        # 计算访问频率
        sorted_entries = sorted(self._cache.values(), key=lambda e: e.access_count, reverse=True)
        top_entries = sorted_entries[:10] if sorted_entries else []

        return {
            "total_entries": len(self._cache),
            "total_size_bytes": self._total_size,
            "total_size_mb": self._total_size / 1024 / 1024,
            "max_size_mb": self.max_size_bytes / 1024 / 1024,
            "utilization": self._total_size / self.max_size_bytes,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": hit_rate,
            "top_entries": [
                {
                    "key": e.key,
                    "size_bytes": e.size_bytes,
                    "access_count": e.access_count,
                    "score": e.score,
                }
                for e in top_entries
            ],
        }

    def get_optimization_suggestions(self) -> list[dict[str, Any]]:
        """
        获取优化建议

        Returns:
            List[Dict]: 优化建议列表
        """
        suggestions = []
        stats = self.get_statistics()

        # 建议 1: 缓存利用率低
        if stats["utilization"] < 0.5:
            suggestions.append(
                {
                    "type": "increase_cache_size",
                    "priority": "low",
                    "message": f"缓存利用率低 ({stats['utilization']:.1%})，可以考虑减少缓存大小以节省内存",
                    "current_size_mb": stats["total_size_mb"],
                    "max_size_mb": stats["max_size_mb"],
                }
            )

        # 建议 2: 缓存利用率高
        if stats["utilization"] > 0.9:
            suggestions.append(
                {
                    "type": "increase_cache_size",
                    "priority": "high",
                    "message": f"缓存利用率高 ({stats['utilization']:.1%})，建议增加缓存大小以提高命中率",
                    "current_size_mb": stats["total_size_mb"],
                    "max_size_mb": stats["max_size_mb"],
                }
            )

        # 建议 3: 命中率低
        if stats["hit_rate"] < 0.7:
            suggestions.append(
                {
                    "type": "improve_cache_strategy",
                    "priority": "high",
                    "message": f"缓存命中率低 ({stats['hit_rate']:.1%})，建议调整缓存策略或增加缓存时间",
                    "hit_rate": stats["hit_rate"],
                }
            )

        # 建议 4: 大数据量条目
        large_entries = [e for e in self._cache.values() if e.size_bytes > 1024 * 100]  # > 100KB
        if len(large_entries) > 5:
            suggestions.append(
                {
                    "type": "optimize_large_entries",
                    "priority": "medium",
                    "message": f"发现 {len(large_entries)} 个大数据量条目（>100KB），建议优化或拆分",
                    "large_entries_count": len(large_entries),
                }
            )

        return suggestions

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._total_size = 0

        self._db.execute("DELETE FROM cache_entries")

        _log.info("🗑️ [Cache] Cache cleared")

    def validate_internal_state(self) -> bool:
        """验证内部状态"""
        return os.path.exists(self.db_path)


# 全局单例
SmartCache = SmartCacheManager()
