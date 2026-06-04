"""Multi-agent conversation framework.

Port of agentmesh patterns/conversation.ts, autogen/{ConversationAgent,
GroupChat, HumanProxy, types}. Provides ConversationAgent, GroupChat,
HumanProxy, and three conversation modes with full asyncio support.
"""

from __future__ import annotations

import asyncio
import enum
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

LLMExecutor = Callable[[str], Awaitable[str]]
ToolHandler = Callable[[dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]]
HumanInputHandler = Callable[["HumanInterventionRequest"], Awaitable["HumanInterventionResponse"]]


# -- Enums --

class MessageType(str, enum.Enum):  # noqa: UP042 — StrEnum requires Python 3.11+
    """Types of messages in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    HUMAN = "human"


class SpeakerSelectionMethod(str, enum.Enum):  # noqa: UP042 — StrEnum requires Python 3.11+
    """Strategy for selecting the next speaker in a group chat."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    FIXED = "fixed"
    AUTO = "auto"


class ConversationMode(str, enum.Enum):  # noqa: UP042 — StrEnum requires Python 3.11+
    """Mode of conversation flow."""

    SEQUENTIAL = "sequential"
    ROUND_ROBIN = "round_robin"
    HIERARCHICAL = "hierarchical"


class InterventionType(str, enum.Enum):  # noqa: UP042 — StrEnum requires Python 3.11+
    """Type of human intervention request."""

    APPROVAL = "approval"
    FEEDBACK = "feedback"
    CONFIRMATION = "confirmation"
    INTERVENTION = "intervention"
    INPUT = "input"


# -- Data structures --

@dataclass
class Message:
    """A single message exchanged between participants."""

    id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    sender: str = ""
    sender_id: str = ""
    content: str = ""
    msg_type: MessageType = MessageType.ASSISTANT
    round: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""


@dataclass
class ToolDef:
    name: str
    description: str = ""
    handler: ToolHandler | None = None


@dataclass
class HumanInterventionRequest:
    id: str = field(default_factory=lambda: f"hreq_{uuid.uuid4().hex[:8]}")
    intervention_type: InterventionType = InterventionType.INPUT
    message: str = ""
    options: list[str] | None = None
    sender_id: str = ""
    sender_name: str = ""
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class HumanInterventionResponse:
    request_id: str = ""
    response: str = ""
    approved: bool | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversationConfig:
    agents: list[str] = field(default_factory=list)
    max_rounds: int = 10
    speaker_selection: SpeakerSelectionMethod = SpeakerSelectionMethod.ROUND_ROBIN
    pass_context: bool = True


@dataclass
class ConversationResult:
    success: bool = True
    conclusion: str = ""
    history: list[Message] = field(default_factory=list)
    final_round: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# -- ConversationAgent --

class ConversationAgent:
    """Agent that can send, receive, and generate messages."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_message: str = "",
        tools: list[ToolDef] | None = None,
        llm: LLMExecutor | None = None,
    ) -> None:
        self.id = agent_id
        self.name = name
        self.system_message = system_message
        self.llm = llm
        self._tools: dict[str, ToolDef] = {t.name: t for t in (tools or [])}
        self._is_speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def create_message(self, content: str, msg_type: MessageType = MessageType.ASSISTANT, metadata: dict[str, Any] | None = None) -> Message:
        return Message(sender=self.name, sender_id=self.id, content=content, msg_type=msg_type, metadata=metadata or {})

    async def reply(self, history: list[Message], task: str = "") -> Message:
        self._is_speaking = True
        try:
            if self.llm:
                parts = [f"[System] {self.system_message}"] if self.system_message else []
                if task:
                    parts.append(f"[Task] {task}")
                parts.extend(f"[{m.sender}] {m.content}" for m in history)
                parts.append(f"[{self.name}] Please respond:")
                content = await self.llm("\n\n".join(parts))
            else:
                content = f"[{self.name} reply - no LLM]"
            return self.create_message(content)
        finally:
            self._is_speaking = False


# ---------------------------------------------------------------------------
# HumanProxy
# ---------------------------------------------------------------------------

class HumanProxy(ConversationAgent):
    """Agent that can request human intervention."""

    def __init__(self, agent_id: str, name: str = "Human", system_message: str = "", input_handler: HumanInputHandler | None = None, auto_approve: bool = False, timeout: float = 60.0) -> None:
        super().__init__(agent_id=agent_id, name=name, system_message=system_message)
        self._input_handler = input_handler
        self._auto_approve = auto_approve
        self._timeout = timeout
        self._pending: dict[str, HumanInterventionRequest] = {}

    async def request_intervention(self, intervention_type: InterventionType, message: str, options: list[str] | None = None, context: dict[str, Any] | None = None) -> HumanInterventionResponse:
        request = HumanInterventionRequest(intervention_type=intervention_type, message=message, options=options, sender_id=self.id, sender_name=self.name, context=context or {})
        if self._auto_approve and intervention_type == InterventionType.APPROVAL:
            return HumanInterventionResponse(request_id=request.id, response="auto-approved", approved=True)
        self._pending[request.id] = request
        if self._input_handler:
            try:
                response = await asyncio.wait_for(self._input_handler(request), timeout=self._timeout)
                self._pending.pop(request.id, None)
                return response
            except TimeoutError:
                self._pending.pop(request.id, None)
                raise
        self._pending.pop(request.id, None)
        return HumanInterventionResponse(request_id=request.id, response="[human input not configured]")

    async def confirm(self, message: str) -> bool:
        r = await self.request_intervention(InterventionType.CONFIRMATION, message, ["confirm", "cancel"])
        return r.response == "confirm" or bool(r.approved)

    async def approve(self, message: str, context: dict[str, Any] | None = None) -> HumanInterventionResponse:
        return await self.request_intervention(InterventionType.APPROVAL, message, ["approve", "reject"], context)

    async def get_feedback(self, message: str) -> str:
        return (await self.request_intervention(InterventionType.FEEDBACK, message)).response

    async def provide_input(self, message: str) -> str:
        return (await self.request_intervention(InterventionType.INPUT, message)).response

    def handle_response(self, request_id: str, response: str = "", approved: bool | None = None) -> None:
        self._pending.pop(request_id, None)

    def has_pending(self) -> bool:
        return bool(self._pending)

    def get_pending(self) -> list[HumanInterventionRequest]:
        return list(self._pending.values())

    def cancel_all(self) -> None:
        self._pending.clear()


# ---------------------------------------------------------------------------
# Speaker selectors
# ---------------------------------------------------------------------------

class _RoundRobinSelector:
    def select(self, agents: list[str], last_speaker: str | None) -> str:
        return agents[0] if last_speaker is None else agents[(agents.index(last_speaker) + 1) % len(agents)]


class _RandomSelector:
    def select(self, agents: list[str], last_speaker: str | None) -> str:
        import secrets
        candidates = [a for a in agents if a != last_speaker] if last_speaker else agents
        return candidates[secrets.randbelow(len(candidates))]


class _FixedSelector:
    def __init__(self, fixed: str) -> None:
        self._fixed = fixed

    def select(self, agents: list[str], last_speaker: str | None) -> str:
        return self._fixed


class GroupChat:
    """Multi-agent group chat with speaker selection and event emission."""

    def __init__(self, agents: list[ConversationAgent], max_round: int = 50, speaker_method: SpeakerSelectionMethod = SpeakerSelectionMethod.ROUND_ROBIN, fixed_speaker: str | None = None) -> None:
        self.agents: dict[str, ConversationAgent] = {a.id: a for a in agents}
        self.max_round = max_round
        self._history: list[Message] = []
        self._current_speaker: str | None = None
        self._round = 0
        self._is_active = False
        self._listeners: list[Callable[[str, Any], Awaitable[None]]] = []
        if speaker_method == SpeakerSelectionMethod.FIXED and fixed_speaker:
            self._selector: _RoundRobinSelector | _RandomSelector | _FixedSelector = _FixedSelector(fixed_speaker)
        elif speaker_method == SpeakerSelectionMethod.RANDOM:
            self._selector = _RandomSelector()
        else:
            self._selector = _RoundRobinSelector()

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def round(self) -> int:
        return self._round

    def on(self, event_type: str, handler: Callable[[Any], Awaitable[None]]) -> None:
        self._listeners.append(lambda et, d: handler(d) if et == event_type else asyncio.sleep(0))

    async def _emit(self, event_type: str, data: Any) -> None:
        for listener in self._listeners:
            await listener(event_type, data)

    def select_next_speaker(self) -> str:
        return self._selector.select(list(self.agents.keys()), self._current_speaker)

    async def run(self, initial_message: str | None = None) -> list[Message]:
        self._is_active = True
        start_time = time.time()
        if initial_message:
            msg = Message(sender="User", sender_id="user", content=initial_message, msg_type=MessageType.USER)
            self._history.append(msg)
            await self._emit("message", msg)
        try:
            while self._round < self.max_round and self._is_active:
                speaker_id = self.select_next_speaker()
                speaker = self.agents.get(speaker_id)
                if speaker is None:
                    raise ValueError(f"Speaker {speaker_id!r} not found")
                self._current_speaker = speaker_id
                self._round += 1
                await self._emit("speaker_changed", {"speaker_id": speaker_id, "speaker_name": speaker.name, "round": self._round})
                reply = await speaker.reply(self._history)
                reply.round = self._round
                self._history.append(reply)
                await self._emit("message", reply)
                await self._emit("round_ended", {"round": self._round, "speaker_id": speaker_id})
        finally:
            self._is_active = False
            await self._emit("chat_ended", {"total_rounds": self._round, "total_messages": len(self._history), "duration": time.time() - start_time})
        return self._history

    def add_message(self, msg: Message) -> None:
        self._history.append(msg)

    def reset(self) -> None:
        self._history.clear()
        self._current_speaker = None
        self._round = 0
        self._is_active = False

    def get_agent(self, agent_id: str) -> ConversationAgent | None:
        return self.agents.get(agent_id)

    def agent_ids(self) -> list[str]:
        return list(self.agents.keys())


async def run_conversation(
    mode: ConversationMode,
    agents: list[ConversationAgent],
    task: str,
    max_rounds: int = 5,
    llm: LLMExecutor | None = None,
    manager: ConversationAgent | None = None,
) -> ConversationResult:
    """Run a multi-agent conversation in the specified mode."""
    history: list[Message] = []

    if mode == ConversationMode.SEQUENTIAL:
        round_num = 1
        idx = 0
        while round_num <= max_rounds:
            speaker = agents[idx % len(agents)]
            reply = await speaker.reply(history, task)
            reply.round = round_num
            history.append(reply)
            idx += 1
            if idx % len(agents) == 0:
                round_num += 1

    elif mode == ConversationMode.ROUND_ROBIN:
        for r in range(1, max_rounds + 1):
            for agent in agents:
                reply = await agent.reply(history, task)
                reply.round = r
                history.append(reply)

    elif mode == ConversationMode.HIERARCHICAL:
        mgr = manager or agents[0]
        workers = agents[1:] if len(agents) > 1 else agents
        for r in range(1, max_rounds + 1):
            mgr_reply = await mgr.reply(history, task)
            mgr_reply.round = r
            history.append(mgr_reply)
            for worker in workers:
                wk_reply = await worker.reply(history, task)
                wk_reply.round = r
                history.append(wk_reply)
            summary = await mgr.reply(history, f"Summarise round {r}")
            summary.content = f"[Round {r} Summary] {summary.content}"
            summary.round = r
            history.append(summary)

    else:
        raise ValueError(f"Unknown conversation mode: {mode}")

    last = history[-3:] if len(history) >= 3 else history
    conclusion = f"After {max_rounds} round(s):\n\n" + "\n\n".join(f"[{m.sender}] {m.content}" for m in last) if last else ""
    return ConversationResult(success=True, conclusion=conclusion, history=history, final_round=max_rounds, metadata={"mode": mode.value, "agents": [a.id for a in agents]})


__all__ = [
    "Message", "MessageType", "ToolDef", "ConversationConfig", "ConversationResult",
    "ConversationMode", "SpeakerSelectionMethod", "InterventionType",
    "HumanInterventionRequest", "HumanInterventionResponse",
    "ConversationAgent", "HumanProxy", "GroupChat", "run_conversation",
    "LLMExecutor", "ToolHandler", "HumanInputHandler",
]
