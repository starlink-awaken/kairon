"""Consensus, debate, and research framework for multi-agent collaboration.

Port of agentmesh /patterns/consensus.ts, /patterns/debate.ts,
and /patterns/ResearchFramework.ts.
"""

from __future__ import annotations

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

LLMExecutor = Callable[[str], Awaitable[str]]

# -- Consensus types --

@dataclass
class VoteOption:
    option_id: str = ""
    description: str = ""
    votes: int = 0

@dataclass
class VoteResult:
    winner: VoteOption | None = None
    options: list[VoteOption] = field(default_factory=list)
    consensus_reached: bool = False
    consensus_threshold: float = 0.7
    total_votes: int = 0

@dataclass
class ConsensusMessage:
    speaker: str = ""
    speaker_name: str = ""
    content: str = ""
    round: int = 0
    timestamp: float = field(default_factory=time.time)
    msg_type: str = "opinion"

@dataclass
class ConsensusConfig:
    agents: list[str] = field(default_factory=list)
    topic: str = ""
    max_rounds: int = 5
    consensus_threshold: float = 0.7
    enable_voting: bool = True
    vote_options: list[str] | None = None

@dataclass
class ConsensusResult:
    success: bool = True
    consensus_reached: bool = False
    consensus: str | None = None
    history: list[ConsensusMessage] = field(default_factory=list)
    vote_result: VoteResult | None = None
    final_round: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class ConsensusPattern:
    """Multi-agent consensus with opinion gathering, proposals, and voting."""

    def __init__(self, config: ConsensusConfig, llm: LLMExecutor | None = None) -> None:
        self._config = config
        if config.consensus_threshold <= 0:
            self._config.consensus_threshold = 0.7
        self._llm = llm
        self._history: list[ConsensusMessage] = []
        self._current_round = 1
        self._votes: dict[str, str] = {}
        self._current_vote_result: VoteResult | None = None
        self._terminated = False
        self._consensus: str | None = None

    @property
    def history(self) -> list[ConsensusMessage]:
        return list(self._history)

    @property
    def vote_result(self) -> VoteResult | None:
        return self._current_vote_result

    @property
    def has_consensus(self) -> bool:
        return bool(self._consensus) or bool(self._current_vote_result and self._current_vote_result.consensus_reached)

    async def execute_round(self) -> list[ConsensusMessage]:
        round_msgs: list[ConsensusMessage] = []
        if self._current_round == 1:
            for agent in self._config.agents:
                round_msgs.append(await self._agent_speak(agent, "opinion"))
        else:
            for agent in self._config.agents:
                round_msgs.append(await self._agent_speak(agent, "proposal"))
        if self._config.enable_voting and self._current_round >= 2:
            await self._collect_votes()
            self._current_vote_result = self._tally_votes()
            if self._current_vote_result.consensus_reached:
                self._consensus = self._current_vote_result.winner.description if self._current_vote_result.winner else None
                self._terminated = True
        self._current_round += 1
        return round_msgs

    async def run(self) -> ConsensusResult:
        while not self._terminated and self._current_round <= self._config.max_rounds:
            await self.execute_round()
        if not self._consensus:
            self._consensus = await self._generate_final_proposal()
        return ConsensusResult(
            success=True,
            consensus_reached=bool(self._current_vote_result and self._current_vote_result.consensus_reached),
            consensus=self._consensus, history=self._history,
            vote_result=self._current_vote_result, final_round=self._current_round - 1,
            metadata={"topic": self._config.topic, "agents": list(self._config.agents), "threshold": self._config.consensus_threshold},
        )

    def _build_context(self) -> str:
        return "\n\n".join(f"{m.speaker_name}: {m.content}" for m in self._history)

    async def _agent_speak(self, agent: str, msg_type: str) -> ConsensusMessage:
        context = self._build_context()
        if self._llm:
            label = "opinion" if msg_type == "opinion" else "proposal"
            prompt = f"Topic: {self._config.topic}\n\nPrevious:\n{context}\n\nAs {agent}, give your {label}."
            content = await self._llm(prompt)
        else:
            content = f"[{agent} {msg_type}]"
        msg = ConsensusMessage(speaker=agent, speaker_name=agent, content=content, round=self._current_round, msg_type=msg_type)
        self._history.append(msg)
        return msg

    async def _collect_votes(self) -> None:
        options = self._config.vote_options
        if not options:
            return
        for agent in self._config.agents:
            if self._llm:
                opts_str = "\n".join(f"{i+1}. {o}" for i, o in enumerate(options))
                resp = await self._llm(f"Topic: {self._config.topic}\n\n{opts_str}\n\nAs {agent}, choose one option (reply with number only).")
                match = re.search(r"(\d+)", resp)
                if match and 1 <= int(match.group(1)) <= len(options):
                    self._votes[agent] = options[int(match.group(1)) - 1]
                else:
                    self._votes[agent] = options[0]
            else:
                self._votes[agent] = options[0]

    def _tally_votes(self) -> VoteResult:
        counts: dict[str, int] = {}
        for vote in self._votes.values():
            counts[vote] = counts.get(vote, 0) + 1
        total = len(self._votes) or 1
        opts = [VoteOption(option_id=d, description=d, votes=c) for d, c in counts.items()]
        winner = max(opts, key=lambda o: o.votes) if opts else None
        pct = winner.votes / total if winner else 0
        return VoteResult(winner=winner, options=opts, consensus_reached=pct >= self._config.consensus_threshold, consensus_threshold=self._config.consensus_threshold, total_votes=len(self._votes))

    async def _generate_final_proposal(self) -> str:
        if self._llm:
            return await self._llm(f"Topic: {self._config.topic}\n\nAfter {self._current_round - 1} rounds, no consensus. Generate final recommendation:\n\n{self._build_context()}")
        return "No consensus reached."

    def add_consensus(self, consensus: str) -> None:
        self._consensus = consensus
        self._terminated = True

    def cast_vote(self, agent: str, option: str) -> None:
        self._votes[agent] = option


def calculate_agreement(votes: dict[str, str]) -> float:
    if not votes:
        return 0.0
    vals = list(votes.values())
    return sum(1 for v in vals if v == vals[0]) / len(vals) if vals[0] else 0.0

async def quick_consensus(topic: str, agents: list[str], llm: LLMExecutor | None = None, max_rounds: int = 3, vote_options: list[str] | None = None, threshold: float = 0.7) -> ConsensusResult:
    return await ConsensusPattern(ConsensusConfig(agents=agents, topic=topic, max_rounds=max_rounds, consensus_threshold=threshold, enable_voting=bool(vote_options), vote_options=vote_options), llm=llm).run()


# -- Debate types --

@dataclass
class DebateMessage:
    side: str = "pro"
    role: str = ""
    speaker_name: str = ""
    content: str = ""
    round: int = 0
    timestamp: float = field(default_factory=time.time)
    argument_type: str = "argument"

@dataclass
class DebateConfig:
    topic: str = ""
    pro_agent: str = ""
    con_agent: str = ""
    moderator: str | None = None
    max_rounds: int = 3
    enable_moderator_summary: bool = True

@dataclass
class DebateResult:
    success: bool = True
    pro_position: str = ""
    con_position: str = ""
    moderator_summary: str | None = None
    conclusion: str = ""
    history: list[DebateMessage] = field(default_factory=list)
    final_round: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

class DebatePattern:
    """Structured pro/con debate with optional moderator."""

    def __init__(self, config: DebateConfig, llm: LLMExecutor | None = None) -> None:
        self._config = config
        if config.max_rounds <= 0:
            self._config.max_rounds = 3
        self._llm = llm
        self._history: list[DebateMessage] = []
        self._current_round = 1

    @property
    def history(self) -> list[DebateMessage]:
        return list(self._history)

    async def _make_argument(self, side: str, agent: str, label: str, arg_type: str) -> DebateMessage:
        ctx = "\n\n".join(f"{m.speaker_name}: {m.content}" for m in self._history)
        if self._llm:
            side_label = "FOR" if side == "pro" else "AGAINST"
            prompt = f"Debate: {self._config.topic}\nRound: {self._current_round}\n\nYou argue {side_label}.\n\n{ctx}\n\nPresent your {label}."
            content = await self._llm(prompt)
        else:
            content = f"[{side} {arg_type} round {self._current_round}]"
        msg = DebateMessage(side=side, role=agent, speaker_name=f"{side.title()} - {agent}", content=content, round=self._current_round, argument_type=arg_type)
        self._history.append(msg)
        return msg

    async def execute_round(self) -> list[DebateMessage]:
        msgs: list[DebateMessage] = []
        arg_type = "opening" if self._current_round == 1 else "argument"
        msgs.append(await self._make_argument("pro", self._config.pro_agent, "argument", arg_type))
        msgs.append(await self._make_argument("con", self._config.con_agent, "rebuttal", "rebuttal"))
        if self._config.moderator and self._config.enable_moderator_summary:
            ctx = "\n\n".join(f"{m.speaker_name}: {m.content}" for m in self._history)
            if self._llm:
                summary = await self._llm(f"Debate: {self._config.topic}\n\nSummarise this round:\n{ctx}")
            else:
                summary = "[Moderator summary]"
            msg = DebateMessage(side="neutral", role=self._config.moderator, speaker_name=f"Moderator - {self._config.moderator}", content=summary, round=self._current_round, argument_type="summary")
            self._history.append(msg)
            msgs.append(msg)
        self._current_round += 1
        return msgs

    async def run(self) -> DebateResult:
        while self._current_round <= self._config.max_rounds:
            await self.execute_round()
        pro = "\n\n".join(m.content for m in self._history if m.side == "pro")
        con = "\n\n".join(m.content for m in self._history if m.side == "con")
        summaries = [m for m in self._history if m.side == "neutral"]
        final_s = summaries[-1].content if summaries else None
        return DebateResult(success=True, pro_position=pro, con_position=con, moderator_summary=final_s, conclusion=final_s or "Debate concluded.", history=self._history, final_round=self._current_round - 1, metadata={"topic": self._config.topic, "pro": self._config.pro_agent, "con": self._config.con_agent, "moderator": self._config.moderator})

    def get_pro_position(self) -> str:
        return "\n\n".join(m.content for m in self._history if m.side == "pro")

    def get_con_position(self) -> str:
        return "\n\n".join(m.content for m in self._history if m.side == "con")

    def get_moderator_summary(self) -> str | None:
        neutrals = [m for m in self._history if m.side == "neutral"]
        return neutrals[-1].content if neutrals else None


async def quick_debate(topic: str, pro_agent: str, con_agent: str, llm: LLMExecutor | None = None, max_rounds: int = 3, moderator: str | None = None) -> DebateResult:
    return await DebatePattern(DebateConfig(topic=topic, pro_agent=pro_agent, con_agent=con_agent, moderator=moderator, max_rounds=max_rounds, enable_moderator_summary=moderator is not None), llm=llm).run()


# -- Research Framework --

@dataclass
class PhaseConfig:
    phase: str = ""
    name: str = ""
    description: str = ""
    duration: str = ""
    agents: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)

@dataclass
class ResearchConfig:
    topic: str = ""
    depth: str = "standard"
    focus_areas: list[str] = field(default_factory=list)

@dataclass
class PhaseOutput:
    phase: str = ""
    content: str = ""
    key_findings: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

@dataclass
class ResearchResult:
    topic: str = ""
    depth: str = "standard"
    phases: dict[str, PhaseOutput] = field(default_factory=dict)
    final_report: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

RESEARCH_PHASES: list[PhaseConfig] = [
    PhaseConfig(phase="reconnaissance", name="Knowledge Reconnaissance", description="Establish foundational understanding.", duration="30s", agents=["Researcher"], outputs=["Overview", "Key terms"]),
    PhaseConfig(phase="exploration", name="Breadth Exploration", description="Gather multi-perspective information.", duration="1-3min", agents=["Researcher", "Analyst"], outputs=["Analysis", "Viewpoints"]),
    PhaseConfig(phase="hypothesis", name="Hypothesis Building", description="Form hypotheses from collected data.", duration="30s", agents=["Strategist"], outputs=["Hypotheses", "Methods"]),
    PhaseConfig(phase="verification", name="Deep Verification", description="Verify hypotheses against evidence.", duration="1-5min", agents=["Verifier", "Critic"], outputs=["Evidence", "Counter-examples"]),
    PhaseConfig(phase="synthesis", name="Synthesis & Output", description="Integrate findings into final report.", duration="30s", agents=["Writer"], outputs=["Report", "Conclusion"]),
]

DEPTH_CONFIG: dict[str, dict[str, Any]] = {
    "standard": {"phases": ["reconnaissance", "exploration", "synthesis"], "duration": "2-3 min", "description": "Quick overview"},
    "deep": {"phases": ["reconnaissance", "exploration", "hypothesis", "synthesis"], "duration": "5-10 min", "description": "In-depth understanding"},
    "exhaustive": {"phases": ["reconnaissance", "exploration", "hypothesis", "verification", "synthesis"], "duration": "10-20 min", "description": "Comprehensive research"},
}

class ResearchFramework:
    """Multi-phase research with configurable depth (standard/deep/exhaustive)."""

    def get_phases_for_depth(self, depth: str) -> list[PhaseConfig]:
        depth_info = DEPTH_CONFIG.get(depth)
        if not depth_info:
            return []
        return [p for p in RESEARCH_PHASES if p.phase in depth_info["phases"]]

    def plan(self, config: ResearchConfig) -> dict[str, Any]:
        phases = self.get_phases_for_depth(config.depth)
        agents = sorted({a for p in phases for a in p.agents})
        depth_info = DEPTH_CONFIG.get(config.depth, {})
        return {"phases": phases, "estimated_duration": depth_info.get("duration", "unknown"), "agents": agents}

    async def execute(self, config: ResearchConfig, llm: LLMExecutor | None = None) -> ResearchResult:
        plan_info = self.plan(config)
        phase_outputs: dict[str, PhaseOutput] = {}
        all_src: list[str] = []
        for phase_cfg in plan_info["phases"]:
            prompt = f"# Research: {config.topic}\n## Phase: {phase_cfg.name}\n{phase_cfg.description}\n## Outputs:\n- " + "\n- ".join(phase_cfg.outputs)
            if phase_outputs:
                prompt += "\n## Previous:\n"
                for po in phase_outputs.values():
                    prompt += f"\n{po.phase}: {po.content[:300]}..."
            prompt += f"\n\nBegin {phase_cfg.name}."
            response = await llm(prompt) if llm else f"[{phase_cfg.name}]"
            findings = [ln[2:].strip() for ln in response.split("\n") if ln.startswith("- ")][:5]
            sources = list(set(re.findall(r"\[([^\]]+)\]", response)))
            po = PhaseOutput(phase=phase_cfg.phase, content=response, key_findings=findings or ["No structured findings"], sources=sources)
            phase_outputs[phase_cfg.phase] = po
            all_src.extend(sources)
        if llm:
            sections = "\n\n".join(f"### {po.phase}\n{po.content[:500]}..." for po in phase_outputs.values())
            final_report = await llm(f"# Research Report\n## Topic: {config.topic}\n## Depth: {config.depth}\n\n{sections}\n\nGenerate a structured research report.")
        else:
            final_report = "Research completed."
        return ResearchResult(topic=config.topic, depth=config.depth, phases=phase_outputs, final_report=final_report, metadata={"duration": DEPTH_CONFIG.get(config.depth, {}).get("duration", ""), "sources": len(set(all_src)), "agents": plan_info["agents"]})


async def run_research(config: ResearchConfig, llm: LLMExecutor | None = None) -> ResearchResult:
    return await ResearchFramework().execute(config, llm=llm)


__all__ = [
    "VoteOption", "VoteResult", "ConsensusMessage", "ConsensusConfig", "ConsensusResult",
    "ConsensusPattern", "calculate_agreement", "quick_consensus",
    "DebateMessage", "DebateConfig", "DebateResult", "DebatePattern", "quick_debate",
    "PhaseConfig", "PhaseOutput", "ResearchConfig", "ResearchResult",
    "ResearchFramework", "RESEARCH_PHASES", "DEPTH_CONFIG", "run_research",
    "LLMExecutor",
]
