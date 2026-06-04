"""Intelligence engines — hypothesis, inference, and reasoning extracted from D_Intelligence."""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class Hypothesis:
    hypothesis_id: str
    statement: str
    confidence: Confidence = Confidence.MEDIUM
    evidence: list[str] = field(default_factory=list)
    counter_evidence: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

@dataclass
class Inference:
    inference_id: str
    premises: list[str]
    conclusion: str
    confidence: Confidence = Confidence.MEDIUM
    method: str = "deductive"

class HypothesisEngine:
    """Generate and evaluate hypotheses based on evidence."""

    def __init__(self):
        self._hypotheses: dict[str, Hypothesis] = {}  # type: ignore[annotation-unchecked]

    def generate(self, statement: str, evidence: list[str] | None = None) -> Hypothesis:
        hid = f"hyp_{len(self._hypotheses):04d}"
        h = Hypothesis(hypothesis_id=hid, statement=statement, evidence=evidence or [])
        self._hypotheses[hid] = h
        return h

    def evaluate(self, hypothesis_id: str, new_evidence: list[str]) -> Confidence:
        h = self._hypotheses.get(hypothesis_id)
        if not h:
            return Confidence.LOW
        h.evidence.extend(new_evidence)
        support = len(h.evidence)
        against = len(h.counter_evidence)
        if support > against * 2:
            h.confidence = Confidence.HIGH
        elif support > against:
            h.confidence = Confidence.MEDIUM
        else:
            h.confidence = Confidence.LOW
        return h.confidence

    def refute(self, hypothesis_id: str, counter: str):
        h = self._hypotheses.get(hypothesis_id)
        if h:
            h.counter_evidence.append(counter)

    def list_by_confidence(self, min_confidence: Confidence = Confidence.MEDIUM) -> list[Hypothesis]:
        levels = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
        return sorted([h for h in self._hypotheses.values() if levels[h.confidence] >= levels[min_confidence]],
                      key=lambda h: levels[h.confidence], reverse=True)


class InferenceEngine:
    """Perform logical inference from premises to conclusions."""

    def __init__(self):
        self._inferences: dict[str, Inference] = {}  # type: ignore[annotation-unchecked]

    def infer(self, premises: list[str], conclusion: str, method: str = "deductive") -> Inference:
        iid = f"inf_{len(self._inferences):04d}"
        inf = Inference(inference_id=iid, premises=premises, conclusion=conclusion, method=method)
        self._inferences[iid] = inf
        return inf

    def validate(self, inference_id: str, known_facts: list[str]) -> Confidence:
        inf = self._inferences.get(inference_id)
        if not inf:
            return Confidence.LOW
        matched = sum(1 for p in inf.premises if any(p in fact for fact in known_facts))
        ratio = matched / len(inf.premises) if inf.premises else 0
        if ratio > 0.8:
            inf.confidence = Confidence.HIGH
        elif ratio > 0.4:
            inf.confidence = Confidence.MEDIUM
        else:
            inf.confidence = Confidence.LOW
        return inf.confidence

    def list_recent(self, limit: int = 20) -> list[Inference]:
        return sorted(self._inferences.values(), key=lambda i: i.inference_id, reverse=True)[:limit]


class ReasoningEngine:
    """Combine hypotheses and inferences for multi-step reasoning."""

    def __init__(self):
        self._hypotheses = HypothesisEngine()
        self._inferences = InferenceEngine()

    def reason(self, observations: list[str], goal: str) -> dict:
        """Multi-step reasoning: generate hypotheses, infer conclusions, evaluate."""
        hyps = [self._hypotheses.generate(obs, [obs]) for obs in observations]
        conclusion = f"Given {len(observations)} observations, {goal}"
        premises = [h.statement for h in hyps]
        inf = self._inferences.infer(premises, conclusion)
        confidence = self._inferences.validate(inf.inference_id, observations)
        return {
            "hypotheses": [{"id": h.hypothesis_id, "statement": h.statement,
                            "confidence": h.confidence.value} for h in hyps],
            "inference": {"id": inf.inference_id, "conclusion": inf.conclusion,
                          "confidence": confidence.value},
        }
