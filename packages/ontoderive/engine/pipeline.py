from __future__ import annotations

"""
---
Type: Organ
Status: Active
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Summary: 'D-Logos Pipeline - batch processing pipeline orchestrator with checkpoint support'
Authority: organs/D-Logos/AGENTS.md
Tags:
- pipeline
- orchestrator
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Pipeline ≡ Pipeline
# 内涵 ≝ {Pipeline}
# 外延 ≝ {e | e ∈ D-Logos ∧ implements(e, Pipeline)}
# 功能 ⊢ {Init_Pipeline, Execute_Pipeline, Validate_Pipeline}
# =============================================================================

"""D-Logos Pipeline - 批量处理管道

提供高效的批量文档-代码对齐处理能力:
- Pipeline API 设计
- 并行扫描支持
- 100+ 文件批量处理
- 失败隔离机制
- 进度追踪
- 断点续传

Phase 3.2 Task 6: 批量处理能力
"""

import logging
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Re-export models for backwards compatibility
from .pipeline_models import (
    BatchItem,
    BatchResult,
    PipelineState,
    PipelineStatus,
    ProgressInfo,
    StepResult,  # noqa: F401
    StepStatus,
)
from .pipeline_steps import (
    AgentContextStep,
    AlignStep,
    BatchAlignStep,
    BatchEvolveStep,
    BatchScanStep,
    BatchValidateStep,
    EvolveStep,
    PipelineStep,
    RootNamespaceStep,
    ScanStep,
    SectionIndexStep,
    ValidateStep,
)


class BaseMembrane:
    """Minimal stub used when the nucleus is not present."""

    def __init__(self, metadata_path: str = "unknown") -> None:
        self.metadata_path = metadata_path
        self.organ_name = metadata_path.split("/")[-1].replace(".py", "")
        self.organ_id = "stub-id"
        self._status = "active"

    def initialize(self) -> None:
        self._status = "active"

    def shutdown(self) -> None:
        self._status = "inactive"

    def call(self, *a: object, **kw: object) -> dict[str, object]:
        return {}

    @property
    def status(self) -> str:
        return getattr(self, "_status", "inactive")

    @status.setter
    def status(self, v: str) -> None:
        self._status = v


# ============================================================
# Doc Governance: Mechanism 5 — Layer Authority Table
# ============================================================

# LAYER_AUTHORITY: Section conflict-resolution precedence.
# When the alignment engine detects conflicting information between sections,
# the section with the LOWER weight number is authoritative (1 = highest authority).
# This is a DOCUMENTED DECISION — enforcement will be automated in Phase 2
# after conflict data has been collected.
LAYER_AUTHORITY: dict[str, int] = {
    "20-architecture": 1,  # Highest authority: canonical design truth
    "60-api": 2,  # API contracts
    "10-strategy": 3,  # Strategic direction
    "25-implementation": 4,  # Implementation details
    "30-user-guides": 5,  # User-facing docs
    "40-operations": 6,  # Operations
    "50-reference": 7,  # Reference material
    "00-overview": 8,  # Entry-point docs
    "90-internal": 9,  # Internal only
}

# ============================================================
# End Mechanism 5
# ============================================================

_log = logging.getLogger(__name__)

# ============================================================
# Pipeline 主类
# ============================================================


class Pipeline:
    """D-Logos 批量处理管道

    支持链式调用、并行处理、失败隔离、进度追踪和断点续传。

    Usage:
        pipeline = Pipeline(root_path)
        pipeline.add_step(ScanStep())
        pipeline.add_step(AlignStep())
        pipeline.add_step(ValidateStep())
        pipeline.add_step(EvolveStep())
        result = pipeline.run()

        # 或使用链式调用
        result = (Pipeline(root_path)
            .add_step(ScanStep())
            .add_step(AlignStep())
            .add_step(ValidateStep())
            .run())
    """

    def __init__(
        self,
        root: Path | str = Path("."),
        checkpoint_dir: Path | str | None = None,
        enable_checkpoint: bool = True,
        max_workers: int = 4,
    ) -> None:
        self.status = "active"
        self.root = Path(root)
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else self.root / ".dlogos" / "checkpoints"
        self.enable_checkpoint = enable_checkpoint
        self.max_workers = max_workers

        self._steps: list[PipelineStep] = []
        self._state: PipelineState | None = None

    def add_step(self, step: PipelineStep) -> Pipeline:
        """添加步骤（支持链式调用）"""
        self._steps.append(step)
        return self

    def remove_step(self, name: str) -> bool:
        """移除步骤"""
        for i, step in enumerate(self._steps):
            if step.name == name:
                self._steps.pop(i)
                return True
        return False

    def clear_steps(self) -> None:
        """清空所有步骤"""
        self._steps.clear()

    def health_check(self) -> dict[str, Any]:
        """Return operational health metrics."""
        state = self._state
        return {
            "status": "healthy",
            "organ": "Pipeline",
            "steps_registered": len(self._steps),
            "pipeline_id": state.pipeline_id if state else None,
            "pipeline_status": state.status.value if state else "not_started",
            "checkpoint_enabled": self.enable_checkpoint,
        }

    def _require_state(self) -> PipelineState:
        """Return the active pipeline state after initialization."""
        state = self._state
        assert state is not None
        return state

    def run(
        self,
        resume: bool = False,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> PipelineState:
        """运行管道

        Args:
            resume: 是否从断点续传
            progress_callback: 进度回调函数

        Returns:
            PipelineState: 管道执行状态
        """
        # 初始化或恢复状态
        if resume and self._can_resume():
            state = self._load_checkpoint()
            if state and state.status == PipelineStatus.COMPLETED:
                _log.info("管道已完成，从头开始运行")
                state = self._create_state()
            self._state = state or self._create_state()
        else:
            self._state = self._create_state()

        state = self._require_state()

        context = {"root": self.root, "max_workers": self.max_workers}

        # 设置进度回调
        if progress_callback:
            for step in self._steps:
                step.set_progress_callback(progress_callback)

        try:
            state.status = PipelineStatus.RUNNING

            for step in self._steps:
                # 检查是否已跳过
                if step.name in state.steps:
                    prev_result = state.steps[step.name]
                    if prev_result.status == StepStatus.COMPLETED:
                        _log.info("跳过步骤: {step.name} (已完成)")
                        continue

                _log.info("\n{'='*50}")
                _log.info("执行步骤: {step.name}")
                _log.info("{'='*50}")

                # 执行步骤
                result = step.execute(context, state.progress)

                # 保存步骤结果
                state.steps[step.name] = result
                state.progress.current = step.name

                # 保存检查点
                if self.enable_checkpoint:
                    state.save()

                # 检查失败
                if result.status == StepStatus.FAILED:
                    _log.info("步骤失败: {step.name}")
                    _log.info("错误: {result.error}")
                    state.status = PipelineStatus.FAILED
                    break

            # 全部完成
            if state.status == PipelineStatus.RUNNING:
                state.status = PipelineStatus.COMPLETED
                state.end_time = time.time()

                # 清理检查点
                if self.enable_checkpoint and state.checkpoint_path:
                    state.checkpoint_path.unlink(missing_ok=True)

        except (TypeError, ValueError, AttributeError, RuntimeError, OSError) as e:
            state.status = PipelineStatus.FAILED
            state.metadata["error"] = str(e)
            _log.info("管道执行出错: {e}")

        # 最终保存
        if self.enable_checkpoint:
            state.save()

        return state

    def run_batch(
        self,
        items: list[BatchItem],
        steps: list[str] | None = None,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> BatchResult:
        """运行批量处理

        Args:
            items: 批量处理项
            steps: 要执行的步骤列表 (默认: ["scan", "align", "validate"])
            progress_callback: 进度回调

        Returns:
            BatchResult: 批量处理结果
        """
        steps = steps or ["scan", "align", "validate"]
        start_time = time.time()

        # 创建批量步骤
        batch_steps = []
        if "scan" in steps:
            batch_steps.append(
                BatchScanStep(
                    items=items,
                    parallel=True,
                    max_workers=self.max_workers,
                )
            )
        if "align" in steps:
            batch_steps.append(
                BatchAlignStep(
                    items=items,
                    parallel=True,
                    max_workers=self.max_workers,
                )
            )
        if "validate" in steps:
            batch_steps.append(
                BatchValidateStep(
                    items=items,
                    parallel=True,
                    max_workers=self.max_workers,
                )
            )
        if "evolve" in steps:
            batch_steps.append(
                BatchEvolveStep(
                    items=items,
                    parallel=True,
                    max_workers=self.max_workers,
                )
            )

        # 设置进度回调
        if progress_callback:
            for step in batch_steps:
                step.set_progress_callback(progress_callback)

        # 执行
        context = {"root": self.root, "max_workers": self.max_workers}
        progress = ProgressInfo(total=len(items))

        for step in batch_steps:
            result = step.execute(context, progress)

            if result.status == StepStatus.FAILED:
                _log.info("批量步骤失败: {step.name}")
                break

        duration = time.time() - start_time

        # 统计结果
        completed = sum(1 for i in items if i.status == StepStatus.COMPLETED)
        failed = sum(1 for i in items if i.status == StepStatus.FAILED)

        return BatchResult(
            total=len(items),
            completed=completed,
            failed=failed,
            skipped=0,
            results=items,
            duration=duration,
        )

    def _create_state(self) -> PipelineState:
        """创建新的管道状态"""
        pipeline_id = str(uuid.uuid4())
        checkpoint_path = None

        if self.enable_checkpoint:
            checkpoint_path = self.checkpoint_dir / f"pipeline_{pipeline_id}.json"
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        return PipelineState(
            pipeline_id=pipeline_id,
            status=PipelineStatus.PENDING,
            start_time=time.time(),
            checkpoint_path=checkpoint_path,
        )

    def _can_resume(self) -> bool:
        """检查是否可以恢复"""
        if not self.enable_checkpoint:
            return False

        # 查找最新的检查点
        if not self.checkpoint_dir.exists():
            return False

        checkpoints = list(self.checkpoint_dir.glob("pipeline_*.json"))
        if not checkpoints:
            return False

        return True

    def _load_checkpoint(self) -> PipelineState | None:
        """加载检查点"""
        if not self.checkpoint_dir.exists():
            return None

        checkpoints = sorted(
            self.checkpoint_dir.glob("pipeline_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not checkpoints:
            return None

        try:
            state = PipelineState.load(checkpoints[0])
            _log.info("从检查点恢复: {state.pipeline_id}")
            _log.info("状态: {state.status.value}")
            return state
        except (OSError, ValueError):
            _log.info("加载检查点失败")
            return None

    def get_progress(self) -> ProgressInfo:
        """获取当前进度"""
        return self._state.progress if self._state else ProgressInfo()

    def get_results(self) -> dict[str, dict[str, Any]]:
        """获取所有步骤的结果"""
        if not self._state:
            return {}

        return {name: result.to_dict() for name, result in self._state.steps.items()}


# ============================================================
# 便捷函数
# ============================================================


def create_scan_pipeline(
    root: Path | str = Path("."),
    docs_dir: Path | str | None = None,
    code_dir: Path | str | None = None,
    parallel: bool = True,
    max_workers: int = 4,
) -> Pipeline:
    """创建扫描管道"""
    pipeline = Pipeline(root, max_workers=max_workers)
    pipeline.add_step(
        ScanStep(
            docs_dir=Path(docs_dir) if docs_dir else None,
            code_dir=Path(code_dir) if code_dir else None,
            parallel=parallel,
            max_workers=max_workers,
        )
    )
    return pipeline


def create_full_pipeline(
    root: Path | str = Path("."),
    docs_dir: Path | str | None = None,
    code_dir: Path | str | None = None,
    validate_threshold: float = 90.0,
    evolve_auto_apply: bool = False,
    parallel: bool = True,
    max_workers: int = 4,
    enable_doc_governance: bool = True,
) -> Pipeline:
    """创建完整管道（扫描→对齐→验证→演化）

    When ``enable_doc_governance=True`` (default), two doc-governance CI gate
    steps are prepended: :class:`RootNamespaceStep` and :class:`SectionIndexStep`.
    These gates are non-blocking (failures are recorded but do not halt the
    pipeline) and follow the SharedBrain naming-convention standard.
    """
    pipeline = Pipeline(root, max_workers=max_workers)

    # Mechanism 2: Doc governance CI gates (prepended before scan)
    if enable_doc_governance:
        docs_root = Path(docs_dir) if docs_dir else Path(root) / "docs"
        pipeline.add_step(RootNamespaceStep(docs_root=docs_root))
        pipeline.add_step(SectionIndexStep(docs_root=docs_root))
        pipeline.add_step(AgentContextStep(root=Path(root)))

    pipeline.add_step(
        ScanStep(
            docs_dir=Path(docs_dir) if docs_dir else None,
            code_dir=Path(code_dir) if code_dir else None,
            parallel=parallel,
            max_workers=max_workers,
        )
    )
    pipeline.add_step(AlignStep())
    pipeline.add_step(ValidateStep(threshold=validate_threshold))
    pipeline.add_step(EvolveStep(auto_apply=evolve_auto_apply))
    return pipeline


def process_batch(
    paths: list[Path],
    root: Path | str = Path("."),
    steps: list[str] | None = None,
    max_workers: int = 4,
    progress_callback: Callable[[ProgressInfo], None] | None = None,
) -> BatchResult:
    """便捷的批量处理函数

    Args:
        paths: 要处理的路径列表（支持100+文件）
        root: 根目录
        steps: 要执行的步骤
        max_workers: 最大并行数
        progress_callback: 进度回调

    Returns:
        BatchResult: 批量处理结果
    """
    # 创建批量项
    items = BatchItem.from_paths(paths)

    # 设置根目录
    for item in items:
        item.metadata["root"] = root

    # 创建并运行管道
    pipeline = Pipeline(root, max_workers=max_workers)
    return pipeline.run_batch(
        items=items,
        steps=steps,
        progress_callback=progress_callback,
    )
