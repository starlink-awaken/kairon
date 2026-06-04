from __future__ import annotations

"""
---
Type: Service
Status: ACTIVE
Version: 1.0.0
Owner: "@Builder"
Layer: L3
Summary: "Shared prompt templates for the cognitive memory sifter."
Extracted from: SharedBrain D_Memory/organs/services/prompts.py → eidos/prompts.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Prompts ≡ Module
# 内涵 ≝ {Prompts}
# 外延 ≝ {e | e ∈ Eidos ∧ implements(e, Prompts)}
# 功能 ⊢ {Init_Prompts, Execute_Prompts, Validate_Prompts}
# =============================================================================


from typing import Any

# Memory Sifter Prompts

MEMORY_SIFTER_SYSTEM_PROMPT = """
You are the 'Cognitive Sifter' for the SharedBrain B-OS.
Your purpose is to act as a high-precision filter between the vast 'HoloMemory' and the Agent's active 'Working Memory'.

### Core Philosophy:
- **Marginal Utility**: Only recall fragments that provide unique, actionable, or essential context for the current task.
- **Noise Reduction**: Exclude redundant, contradictory, or irrelevant information.
- **Cognitive Economy**: Every token in the prompt costs energy (EU). Be surgical.

### Output Format:
1. Wrap your internal analysis in <think> tags.
2. List the IDs of the 'Winning' fragments in order of utility inside <ranking> tags, separated by commas.
3. If no fragments are relevant, return <ranking></ranking>.
"""


def build_sifter_user_prompt(query: str, nodes: list[dict[str, Any]]) -> str:
    nodes_block = "\n".join([f"ID: {n['key']} | Context: {n['value']}" for n in nodes])
    return f"""
Current Task/Intent:
"{query}"

Candidate Memory Fragments:
{nodes_block}

---
Analyze the fragments and rank the most useful ones.
"""
