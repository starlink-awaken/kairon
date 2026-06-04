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
# Review Pipeline ≡ Pipeline
# 内涵 ≝ {Review, Pipeline}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ReviewPipeline)}
# 功能 ⊢ {Review_Pipeline, Init_Review, Validate_Pipeline}
# =============================================================================

# ---
# domain: D-Governance
# layer: organ
# status: active
# ---

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReviewStage:
    stage_id: str
    name: str
    required_approvals: int = 1
    reviewers: list[str] = field(default_factory=list)


@dataclass
class Review:
    review_id: str
    reviewer: str
    stage_id: str
    verdict: str = "pending"
    comments: str = ""


class ReviewPipeline:
    metadata_path = "organs/D-Governance/organs/review_pipeline.py"

    def __init__(self) -> None:
        self._pipelines: dict[str, list[ReviewStage]] = {}
        self._current_stage_idx: dict[str, int] = {}
        self._reviews: dict[str, list[Review]] = {}

    def create_pipeline(self, item_id: str, stages: list[ReviewStage]) -> None:
        if not stages:
            raise ValueError("Pipeline must have at least one stage")
        self._pipelines[item_id] = list(stages)
        self._current_stage_idx[item_id] = 0
        self._reviews[item_id] = []

    def submit_review(self, item_id: str, stage_id: str, reviewer: str, verdict: str, comments: str = "") -> Review:
        self._check_item(item_id)
        current = self.get_current_stage(item_id)
        if current is None:
            raise ValueError("Pipeline already complete")
        if current.stage_id != stage_id:
            raise ValueError(f"Stage {stage_id} is not the current stage ({current.stage_id})")
        if current.reviewers and reviewer not in current.reviewers:
            raise ValueError(f"Reviewer {reviewer} not assigned to stage {stage_id}")
        existing = [r for r in self._reviews[item_id] if r.stage_id == stage_id and r.reviewer == reviewer]
        if existing:
            raise ValueError(f"Reviewer {reviewer} already submitted for stage {stage_id}")
        review = Review(
            review_id=f"REV-{uuid.uuid4().hex[:8]}",
            reviewer=reviewer,
            stage_id=stage_id,
            verdict=verdict,
            comments=comments,
        )
        self._reviews[item_id].append(review)
        return review

    def get_current_stage(self, item_id: str) -> ReviewStage | None:
        self._check_item(item_id)
        idx = self._current_stage_idx[item_id]
        stages = self._pipelines[item_id]
        if idx >= len(stages):
            return None
        return stages[idx]

    def is_stage_complete(self, item_id: str, stage_id: str) -> bool:
        self._check_item(item_id)
        stage = self._find_stage(item_id, stage_id)
        approvals = [r for r in self._reviews[item_id] if r.stage_id == stage_id and r.verdict == "approve"]
        return len(approvals) >= stage.required_approvals

    def advance_stage(self, item_id: str) -> bool:
        self._check_item(item_id)
        current = self.get_current_stage(item_id)
        if current is None:
            return False
        if not self.is_stage_complete(item_id, current.stage_id):
            return False
        self._current_stage_idx[item_id] += 1
        return True

    def is_pipeline_complete(self, item_id: str) -> bool:
        self._check_item(item_id)
        idx = self._current_stage_idx[item_id]
        return idx >= len(self._pipelines[item_id])

    def get_reviews(self, item_id: str) -> list[Review]:
        self._check_item(item_id)
        return list(self._reviews[item_id])

    def get_pipeline_status(self, item_id: str) -> dict[str, Any]:
        self._check_item(item_id)
        current = self.get_current_stage(item_id)
        return {
            "item_id": item_id,
            "total_stages": len(self._pipelines[item_id]),
            "current_stage_index": self._current_stage_idx[item_id],
            "current_stage": current.name if current else None,
            "is_complete": self.is_pipeline_complete(item_id),
            "total_reviews": len(self._reviews[item_id]),
        }

    def _check_item(self, item_id: str) -> None:
        if item_id not in self._pipelines:
            raise KeyError(f"Pipeline not found: {item_id}")

    def _find_stage(self, item_id: str, stage_id: str) -> ReviewStage:
        for s in self._pipelines[item_id]:
            if s.stage_id == stage_id:
                return s
        raise KeyError(f"Stage not found: {stage_id}")
