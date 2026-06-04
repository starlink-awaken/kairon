from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Meta Validate Persist ≡ Module
# 内涵 ≝ {Meta, Validate, Persist}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, MetaValidatePersist)}
# 功能 ⊢ {Meta_Validate, Validate_Persist, Persist_Init}
# =============================================================================


import json
import logging
import time
from pathlib import Path
from typing import Any

from engine.organs.meta_validate_types import (
    GroundTruth,
)

_log = logging.getLogger(__name__)


class _MetaPersistenceMixin:
    """Ground-truth persistence helpers extracted from MetaValidateEngine.

    Provides _load_ground_truths, load_ground_truth_from_file,
    validate_against_ground_truth, _save_ground_truths,
    _save_validation_history, and add_ground_truth.
    Mixed into MetaValidateEngine in meta_validate.py.
    """

    data_dir: Path
    ground_truths: dict[str, GroundTruth]
    validation_history: list[Any]

    def _load_ground_truths(self) -> None:
        """加载基准真值"""
        gt_file = self.data_dir / "ground_truths.json"
        if gt_file.exists():
            try:
                with open(gt_file, encoding="utf-8") as f:
                    json.load(f)
                    # 简化加载
                    _log.info("✅ 已加载 {len(data.get('ground_truths', []))} 个基准真值")
            except (json.JSONDecodeError, OSError, ValueError):
                _log.info("⚠️  加载基准真值失败: {e}")

    def load_ground_truth_from_file(self, file_path: Path) -> int:
        """从JSON文件加载基准真值注解

        Args:
            file_path: 包含注解的JSON文件路径

        Returns:
            加载的注解数量
        """
        import time

        gt_file = Path(file_path)
        if not gt_file.exists():
            _log.info("⚠️  文件不存在: {gt_file}")
            return 0

        try:
            with open(gt_file, encoding="utf-8") as f:
                data = json.load(f)

            annotations = data.get("annotations", [])
            loaded_count = 0

            for ann in annotations:
                # 创建 GroundTruth 对象
                gt = GroundTruth(
                    id=f"{data.get('id', 'GT')}-{ann.get('api_name', 'unknown')}",
                    project=data.get("project", "D-Logos"),
                    version=data.get("version", "1.0.0"),
                    timestamp=data.get("timestamp", time.time()),
                    files={ann.get("module", ""): ann.get("api_name", "")},
                    expected_alignment={
                        "api_name": ann.get("api_name", ""),
                        "signature": ann.get("signature", ""),
                        "description": ann.get("description", ""),
                        "expected_behavior": ann.get("expected_behavior", {}),
                        "validation_criteria": ann.get("validation_criteria", {}),
                    },
                    source=data.get("source", "human_audit"),
                )
                self.ground_truths[gt.id] = gt
                loaded_count += 1

            _log.info("✅ 已从 {gt_file.name} 加载 {loaded_count} 个基准真值注解")
            return loaded_count

        except (json.JSONDecodeError, OSError, ValueError):
            _log.info("⚠️  加载基准真值失败: {e}")
            return 0

    def validate_against_ground_truth(self, gt_id: str | None = None) -> dict[str, Any]:
        """根据基准真值进行验证

        Args:
            gt_id: 可选的基准真值ID，如果为None则验证所有

        Returns:
            验证结果字典
        """
        if gt_id:
            gts = {gt_id: self.ground_truths.get(gt_id)}
        else:
            gts = self.ground_truths

        results = {
            "total": len(gts),
            "passed": 0,
            "failed": 0,
            "details": [],
        }

        for id_, gt in gts.items():
            if gt is None:
                continue

            # 验证逻辑 - 检查expected_alignment是否包含必要的字段
            expected = gt.expected_alignment
            required_fields = ["api_name", "signature", "description"]

            missing = [f for f in required_fields if not expected.get(f)]
            if missing:
                results["failed"] += 1
                results["details"].append(
                    {
                        "id": id_,
                        "status": "failed",
                        "reason": f"Missing fields: {missing}",
                    }
                )
            else:
                results["passed"] += 1
                results["details"].append(
                    {
                        "id": id_,
                        "status": "passed",
                    }
                )

        if results["total"] > 0:
            results["accuracy"] = results["passed"] / results["total"]
        else:
            results["accuracy"] = 0.0

        return results

    def _save_ground_truths(self) -> None:
        """保存基准真值"""
        gt_file = self.data_dir / "ground_truths.json"
        data = {
            "ground_truths": [
                {
                    "id": gt.id,
                    "project": gt.project,
                    "version": gt.version,
                    "timestamp": gt.timestamp,
                    "source": gt.source,
                }
                for gt in self.ground_truths.values()
            ],
            "updated_at": time.time(),
        }
        with open(gt_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_validation_history(self) -> None:
        """保存验证历史"""
        history_file = self.data_dir / "validation_history.json"
        data = {
            "validations": [
                {
                    "id": v.id,
                    "status": v.status.value,
                    "confidence": v.confidence.score,
                    "verified_at": v.verified_at,
                }
                for v in self.validation_history[-100:]  # 保留最近 100 条
            ],
            "updated_at": time.time(),
        }
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_ground_truth(self, ground_truth: GroundTruth) -> None:
        """添加基准真值"""
        self.ground_truths[ground_truth.id] = ground_truth
        self._save_ground_truths()
        _log.info("✅ 已添加基准真值: {ground_truth.id}")
