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
# Knowledge Distiller ≡ Module
# 内涵 ≝ {Knowledge, Distiller}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, KnowledgeDistiller)}
# 功能 ⊢ {Knowledge_Distiller, Init_Knowledge, Validate_Distiller}
# =============================================================================

"""Knowledge Distiller — synthesises experience into reusable memory.

---
Type: Organ
Layer: L4
Domain: D-Memory
Status: ACTIVE
Version: 2.0.0
Owner: '@Prime'
Authority: EC-7/PB-3
Keywords: [knowledge, distillation, learning, patterns, insights]
---

Transforms raw experience records into structured, reusable knowledge units
suitable for storage in FactGraph (as triples) and injection into LLM prompts.

Distillation dimensions:
- action_outcome: what happened as a result of the action
- context_prereq: preconditions that must hold for this knowledge to apply
- success_factor: conditions that contributed to a positive outcome
- failure_mode: conditions that led to a negative outcome

Usage::

    distiller = KnowledgeDistiller()
    result = distiller.distill({"task": "fix_auth", "outcome": "success", "steps": [...]})
    insight = distiller.extract_actionable_insight(result.knowledge_units[0])
    summary = distiller.summarize_pattern("retry_success", evidence_count=12)
"""


import logging

_log = logging.getLogger(__name__)
