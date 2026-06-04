from __future__ import annotations

"""
---
Type: Engine
Status: ACTIVE
Version: 1.0.0
Owner: '@Prime'
Layer: L3
Summary: Memory Archiver - migrates consolidated hot memory to cold Git-based storage.
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Archiver ≡ Module
# 内涵 ≝ {Archiver}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Archiver)}
# 功能 ⊢ {Init_Archiver, Execute_Archiver, Validate_Archiver}
# =============================================================================

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any

from eidos.fact_graph import get_graph

_log = logging.getLogger(__name__)


class MemoryArchiver:
    """记忆归档器：将已固化的热数据迁移至冷存储（本地文件 + Git）。"""

    def __init__(self, graph: Any | None = None) -> None:
        self.graph = graph or get_graph()
        root = os.environ.get("BOS_ROOT", os.getcwd())
        self.archive_dir = os.path.join(root, "organs", "D-Memory", "data", "archive")
        os.makedirs(self.archive_dir, exist_ok=True)

    def archive_consolidated(self) -> int:
        """执行归档操作。"""
        # 查询所有标记为已固化但尚未归档的事实
        # 简化处理：查询 metadata 中包含 "consolidated": True 的项
        facts = self.graph.query()
        to_archive = []
        for f in facts:
            meta = json.loads(f.get("metadata", "{}"))
            if meta.get("consolidated") and not meta.get("archived"):
                to_archive.append(f)

        if not to_archive:
            return 0

        # 写入文件
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(self.archive_dir, f"cold_memory_{batch_id}.json")

        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(to_archive, f, indent=2, ensure_ascii=False)

        # 标记已归档并从热库移除（或保留，取决于策略）
        # 此处选择从热库移除以节省向量索引空间
        with self.graph._get_connection() as conn:
            for fact in to_archive:
                conn.execute("DELETE FROM fact_triples WHERE id = ?", (fact["id"],))
            conn.commit()

        # Invalidate edge cache after raw-SQL deletes
        if hasattr(self.graph, "_edge_cache"):
            self.graph._edge_cache.invalidate_pattern("fact:")

        # 触发 Git 提交 (冷存储持久化)
        self._git_commit(archive_path)

        _log.info(f"✅ [D-Memory-Archiver] Archived {len(to_archive)} facts to {archive_path}")
        return len(to_archive)

    def _git_commit(self, filepath: str) -> None:
        """将归档文件提交至 Git。"""
        try:
            # 仅在 git 仓库环境下执行
            subprocess.run(["git", "add", filepath], check=True, capture_output=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"chore(memory): Archive cold memory {os.path.basename(filepath)}",
                ],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError) as e:
            _log.warning(f"Git commit failed during archiving: {e}")


# Global singleton
global_archiver = MemoryArchiver()
