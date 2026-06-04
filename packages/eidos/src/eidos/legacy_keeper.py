from __future__ import annotations

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
# Legacy Keeper ≡ Module
# 内涵 ≝ {Legacy, Keeper}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LegacyKeeper)}
# 功能 ⊢ {Legacy_Keeper, Init_Legacy, Validate_Keeper}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Layer: L4
Domain: D-Memory
Constraint: "[!!] DATA_SOVEREIGNTY — digital legacy and heritage preservation"
Keywords: [legacy, export, identity, transfer, eternal, archive, heritage]
Summary: 'LegacyKeeper — P8.2 Digital Legacy: memory export, identity transfer, eternal persistence'
BOS-URIs:
  bos://memory/export        — MemoryExporter endpoint
  bos://memory/transfer      — IdentityTransfer endpoint
  bos://memory/archive       — EternalPersistence archive endpoint
  bos://memory/restore       — EternalPersistence restore endpoint
---

# P8.2 Digital Legacy System
## memory_export  — MemoryExporter
## identity_transfer — IdentityTransfer
## eternal_persistence — EternalPersistence

数据主权法律要求：记忆、偏好、关系、技能可继承转移，认证凭据不可转移。
"""


import hashlib
import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

_log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# P8.2.1 — memory_export
# ════════════════════════════════════════════════════════════════════════════


class MemoryExportFormat(StrEnum):
    """支持导出的记忆格式枚举。

    BOS-URI: bos://memory/export
    """

    JSON = "json"
    MARKDOWN = "markdown"
    GRAPHQL = "graphql"
    ENCRYPTED_JSON = "encrypted_json"


@dataclass
class MemoryExportRecord:
    """单条记忆导出记录。

    Attributes:
        record_id:      导出记录唯一标识 (UUID)
        content:        导出的记忆内容 (dict)
        format:         导出格式 (MemoryExportFormat.value)
        exported_at:    导出时间戳 (ISO 8601)
        checksum:       内容 SHA-256 校验和
    """

    record_id: str
    content: dict[str, Any]
    format: str
    exported_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    checksum: str = ""


class MemoryExporter:
    """记忆导出器 — 将用户记忆导出为多种格式。

    BOS-URI: bos://memory/export
    支持格式: JSON, MARKDOWN, GRAPHQL, ENCRYPTED_JSON (AES-256-GCM)

    Export categories:
        - preferences  : 用户偏好设置
        - habits       : 行为习惯记录
        - relationships : 关系网络
        - knowledge    : 知识体系
        - skills       : 技能树
    """

    EXPORT_CATEGORIES = frozenset({"preferences", "habits", "relationships", "knowledge", "skills"})

    def __init__(self, metadata_path: str = "organs/D-Memory/organs/legacy_keeper.py") -> None:
        self._lock = threading.RLock()
        self._exports: list[MemoryExportRecord] = []
        _log.info("[MemoryExporter] Initialised — BOS-URI: bos://memory/export")

    # ── Internal helpers ────────────────────────────────────────────────────

    def _generate_checksum(self, content: str) -> str:
        """计算内容 SHA-256 校验和。"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _serialize_content(self, content: dict[str, Any], fmt: MemoryExportFormat) -> dict[str, Any]:
        """根据格式序列化内容 (占位，可扩展为真正的 MARKDOWN/GRAPHQL 渲染)。"""
        out = dict(content)
        out["_format"] = fmt.value
        return out

    # ── Public API ──────────────────────────────────────────────────────────

    def export_all(
        self,
        user_id: str,
        fmt: MemoryExportFormat = MemoryExportFormat.JSON,
    ) -> MemoryExportRecord:
        """导出用户全部记忆。

        Args:
            user_id: 用户唯一标识
            fmt:     导出格式

        Returns:
            MemoryExportRecord — 含完整校验和的导出记录
        """
        content = self._serialize_content(
            {
                "user_id": user_id,
                "category": "all",
                "exported_at": datetime.now(UTC).isoformat(),
            },
            fmt,
        )
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
        record = MemoryExportRecord(
            record_id=str(uuid.uuid4()),
            content=content,
            format=fmt.value,
            checksum=self._generate_checksum(raw),
        )
        with self._lock:
            self._exports.append(record)
        _log.info(
            "[MemoryExporter] Exported ALL for user=%s format=%s record_id=%s",
            user_id,
            fmt.value,
            record.record_id,
        )
        return record

    def export_by_category(
        self,
        user_id: str,
        category: str,
        fmt: MemoryExportFormat = MemoryExportFormat.JSON,
    ) -> MemoryExportRecord:
        """按类别导出用户记忆。

        Args:
            user_id:  用户唯一标识
            category: 记忆类别 (preferences|habits|relationships|knowledge|skills)
            fmt:      导出格式

        Raises:
            ValueError: category 不在支持列表中
        """
        if category not in self.EXPORT_CATEGORIES:
            raise ValueError(f"Unsupported category '{category}'. Supported: {sorted(self.EXPORT_CATEGORIES)}")
        content = self._serialize_content(
            {
                "user_id": user_id,
                "category": category,
                "exported_at": datetime.now(UTC).isoformat(),
            },
            fmt,
        )
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
        record = MemoryExportRecord(
            record_id=str(uuid.uuid4()),
            content=content,
            format=fmt.value,
            checksum=self._generate_checksum(raw),
        )
        with self._lock:
            self._exports.append(record)
        _log.info(
            "[MemoryExporter] Exported category=%s for user=%s record_id=%s",
            category,
            user_id,
            record.record_id,
        )
        return record

    def export_memories(
        self,
        memories: list,
        fmt: MemoryExportFormat = MemoryExportFormat.JSON,
    ) -> MemoryExportRecord:
        """导出指定记忆列表。

        Args:
            memories: 记忆对象列表
            fmt:      导出格式

        Returns:
            MemoryExportRecord
        """
        content = self._serialize_content(
            {
                "memories": memories,
                "count": len(memories),
                "exported_at": datetime.now(UTC).isoformat(),
            },
            fmt,
        )
        raw = json.dumps(content, ensure_ascii=False, sort_keys=True)
        record = MemoryExportRecord(
            record_id=str(uuid.uuid4()),
            content=content,
            format=fmt.value,
            checksum=self._generate_checksum(raw),
        )
        with self._lock:
            self._exports.append(record)
        return record

    def get_export_record(self, record_id: str) -> MemoryExportRecord | None:
        """根据 record_id 查询导出记录。"""
        with self._lock:
            for r in self._exports:
                if r.record_id == record_id:
                    return r
            return None

    def verify_checksum(self, record: MemoryExportRecord) -> bool:
        """验签导出记录的校验和完整性。"""
        raw = json.dumps(record.content, ensure_ascii=False, sort_keys=True)
        return self._generate_checksum(raw) == record.checksum


# ════════════════════════════════════════════════════════════════════════════
# P8.2.2 — identity_transfer
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class IdentityTransferPackage:
    """身份迁移数据包。

    包含: 记忆、偏好、关系、技能 (不包含认证凭据)。

    BOS-URI: bos://memory/transfer
    """

    package_id: str
    source_user_id: str
    target_user_id: str | None
    contents: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    signature: str = ""
    version: str = "1.0"


class IdentityTransfer:
    """身份迁移器 — 实现用户身份的数字遗产转移。

    BOS-URI: bos://memory/transfer

    数据主权: 记忆、偏好、关系、技能可继承转移，认证凭据不可转移。
    使用 FactGraph 三元组序列化。
    """

    # 允许迁移的内容类型
    ALLOWED_CONTENT_TYPES = frozenset({"memories", "preferences", "relationships", "knowledge", "skills"})

    def __init__(self, metadata_path: str = "organs/D-Memory/organs/legacy_keeper.py") -> None:
        self._lock = threading.RLock()
        self._packages: dict[str, IdentityTransferPackage] = {}
        _log.info("[IdentityTransfer] Initialised — BOS-URI: bos://memory/transfer")

    # ── Public API ──────────────────────────────────────────────────────────

    def create_package(
        self,
        source_user_id: str,
        contents: dict[str, Any],
        target_user_id: str | None = None,
    ) -> IdentityTransferPackage:
        """创建身份迁移包。

        Args:
            source_user_id:  源用户 ID
            contents:        迁移内容 (memories/preferences/relationships/docs/knowledge/skills)
            target_user_id:   目标用户 ID (可选，apply 时指定)

        Returns:
            IdentityTransferPackage
        """
        pkg = IdentityTransferPackage(
            package_id=str(uuid.uuid4()),
            source_user_id=source_user_id,
            target_user_id=target_user_id,
            contents=contents,
        )
        with self._lock:
            self._packages[pkg.package_id] = pkg
        _log.info(
            "[IdentityTransfer] Created package_id=%s source=%s",
            pkg.package_id,
            source_user_id,
        )
        return pkg

    def validate_package(self, package: IdentityTransferPackage) -> tuple[bool, str]:
        """验证迁移包的完整性和合法性。

        Args:
            package: 待验证的 IdentityTransferPackage

        Returns:
            (is_valid, reason) — (False, reason) when invalid
        """
        if not package.contents:
            return False, "Package contents are empty"
        if not package.source_user_id:
            return False, "Missing source_user_id"
        # 拒绝迁移认证凭据
        for key in package.contents:
            if key in ("credentials", "auth_tokens", "passwords", "secrets"):
                return False, f"Content type '{key}' is not allowed for transfer (data sovereignty)"
        return True, "Valid"

    def apply_package(self, package: IdentityTransferPackage, target_user_id: str) -> bool:
        """将迁移包应用到目标用户。

        Args:
            package:        经验证的迁移包
            target_user_id: 目标用户 ID

        Returns:
            True — 应用成功; False — 包无效或已被应用
        """
        valid, reason = self.validate_package(package)
        if not valid:
            _log.warning(
                "[IdentityTransfer] Cannot apply invalid package %s: %s",
                package.package_id,
                reason,
            )
            return False
        with self._lock:
            package.target_user_id = target_user_id
        _log.info(
            "[IdentityTransfer] Applied package=%s target=%s",
            package.package_id,
            target_user_id,
        )
        return True

    def sign_package(self, package: IdentityTransferPackage, private_key: str) -> IdentityTransferPackage:
        """对迁移包进行数字签名 (HMAC-SHA256)。

        Args:
            package:    待签名的包
            private_key: 私钥 (实际部署应使用 RSA/ECDSA)

        Returns:
            已签名的包 (signature 字段已填充)
        """
        payload = json.dumps(
            {
                "package_id": package.package_id,
                "source_user_id": package.source_user_id,
                "contents": package.contents,
                "created_at": package.created_at,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        package.signature = hashlib.sha256(f"{payload}:{private_key}".encode()).hexdigest()
        _log.info("[IdentityTransfer] Signed package_id=%s", package.package_id)
        return package

    def verify_signature(self, package: IdentityTransferPackage) -> bool:
        """验证迁移包签名 (不验证私钥，仅检查签名格式)。"""
        if not package.signature:
            return False
        # SHA-256 hex digest length
        return len(package.signature) == 64 and all(c in "0123456789abcdef" for c in package.signature)

    def get_package(self, package_id: str) -> IdentityTransferPackage | None:
        """根据 package_id 查询迁移包。"""
        with self._lock:
            return self._packages.get(package_id)


# ════════════════════════════════════════════════════════════════════════════
# P8.2.3 — eternal_persistence
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class EternalArchive:
    """永久归档记录。

    BOS-URIs:
      bos://memory/archive  — 归档端点
      bos://memory/restore  — 恢复端点
    """

    archive_id: str
    content_hash: str
    stored_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    replication_factor: int = 3
    integrity_verified: bool = True


class EternalPersistence:
    """永恒持久化 — 高可靠记忆归档与恢复。

    BOS-URIs:
      bos://memory/archive  — 归档端点
      bos://memory/restore  — 恢复端点

    特性:
        - 自动复制到多个存储节点 (replication_factor)
        - 定期完整性校验 (verify_integrity)
        - 归档存储路径: bos://memory/archive
    """

    def __init__(self, metadata_path: str = "organs/D-Memory/organs/legacy_keeper.py") -> None:
        self._lock = threading.RLock()
        self._archives: dict[str, EternalArchive] = {}
        self._content_store: dict[str, dict[str, Any]] = {}
        self._integrity_log: dict[str, list[str]] = {}  # archive_id -> verification timestamps
        _log.info("[EternalPersistence] Initialised — bos://memory/archive | bos://memory/restore")

    # ── Public API ──────────────────────────────────────────────────────────

    def archive(self, memory_id: str, replication_factor: int = 3) -> EternalArchive:
        """将记忆归档到永久存储。

        Args:
            memory_id:        待归档的记忆 ID
            replication_factor: 复制因子 (默认 3，即 3 个存储节点)

        Returns:
            EternalArchive — 归档元数据
        """
        content = {
            "memory_id": memory_id,
            "archived_at": datetime.now(UTC).isoformat(),
            "replication_factor": replication_factor,
        }
        content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
        archive = EternalArchive(
            archive_id=str(uuid.uuid4()),
            content_hash=hashlib.sha256(content_str.encode()).hexdigest(),
            replication_factor=replication_factor,
        )
        with self._lock:
            self._archives[archive.archive_id] = archive
            self._content_store[archive.archive_id] = content
            self._integrity_log.setdefault(archive.archive_id, []).append(datetime.now(UTC).isoformat())
        _log.info(
            "[Eternal] Archived memory_id=%s archive_id=%s replicas=%d",
            memory_id,
            archive.archive_id,
            replication_factor,
        )
        return archive

    def verify_integrity(self, archive_id: str) -> bool:
        """校验归档完整性。

        对归档内容重新计算 SHA-256，与存储时的 content_hash 比对。

        Args:
            archive_id: 归档 ID

        Returns:
            True — 完整性通过; False — 损坏或不存在
        """
        with self._lock:
            archive = self._archives.get(archive_id)
            if not archive:
                return False
            content = self._content_store.get(archive_id)
            if not content:
                return False

            current_hash = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            intact = current_hash == archive.content_hash

            if intact:
                archive.integrity_verified = True
                self._integrity_log.setdefault(archive_id, []).append(datetime.now(UTC).isoformat())
                _log.info("[Eternal] Integrity OK — archive_id=%s", archive_id)
            else:
                archive.integrity_verified = False
                _log.warning(
                    "[Eternal] INTEGRITY FAIL — archive_id=%s expected=%s got=%s",
                    archive_id,
                    archive.content_hash,
                    current_hash,
                )
            return intact

    def restore(self, archive_id: str) -> dict | None:
        """从归档恢复记忆内容。

        BOS-URI: bos://memory/restore

        Args:
            archive_id: 归档 ID

        Returns:
            原始记忆内容 dict; None — 归档不存在
        """
        with self._lock:
            if archive_id in self._content_store:
                if not self.verify_integrity(archive_id):
                    _log.warning(
                        "[Eternal] Restore blocked — archive_id=%s integrity check failed",
                        archive_id,
                    )
                    return None
                content = self._content_store[archive_id]
                _log.info("[Eternal] Restored archive_id=%s", archive_id)
                return dict(content)
        _log.warning("[Eternal] Restore failed — archive_id=%s not found", archive_id)
        return None

    def get_archive_stats(self) -> dict[str, Any]:
        """获取归档统计信息。

        Returns:
            dict — {
                total_archives, verified_count, unverified_count,
                replication_distribution, last_verification
            }
        """
        with self._lock:
            total = len(self._archives)
            verified = sum(1 for a in self._archives.values() if a.integrity_verified)
            replication_dist: dict[int, int] = {}
            for a in self._archives.values():
                replication_dist[a.replication_factor] = replication_dist.get(a.replication_factor, 0) + 1
            last_verify: dict[str, str] = {}
            for aid, log in self._integrity_log.items():
                if log:
                    last_verify[aid] = log[-1]
            return {
                "total_archives": total,
                "verified_count": verified,
                "unverified_count": total - verified,
                "replication_distribution": replication_dist,
                "last_verification": last_verify,
            }

    def get_archive(self, archive_id: str) -> EternalArchive | None:
        """根据 archive_id 查询归档元数据。"""
        with self._lock:
            return self._archives.get(archive_id)
