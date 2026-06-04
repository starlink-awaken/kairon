"""Multi-agent conversation framework.

Provides Agent, ConversationAgent, GroupChat, and HumanProxy
for building multi-agent chat systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A message exchanged between agents."""

    sender: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    """A named participant in a conversation."""

    name: str
    role: str = "assistant"
    system_prompt: str = ""

    def format_prompt(self, context: list[Message]) -> str:
        """Build a prompt string from the conversation context."""
        parts = [f"[System] {self.system_prompt}"] if self.system_prompt else ["[System] You are a helpful assistant."]
        for msg in context:
            parts.append(f"[{msg.sender}] {msg.content}")
        return "\n".join(parts)


class ConversationAgent(Agent):
    """An agent that can send and receive messages."""

    def __init__(
        self,
        name: str,
        role: str = "assistant",
        system_prompt: str = "",
        reply_fn: Any = None,
    ) -> None:
        super().__init__(name=name, role=role, system_prompt=system_prompt)
        self._reply_fn = reply_fn

    def send(self, content: str) -> Message:
        return Message(sender=self.name, content=content)

    def receive(self, message: Message, history: list[Message]) -> Message | None:
        """Process an incoming message and return a reply if possible."""
        if self._reply_fn is None:
            return None
        context = history + [message]
        prompt = self.format_prompt(context)
        reply_content = self._reply_fn(prompt, self.name)
        return Message(sender=self.name, content=reply_content)


class GroupChat:
    """Facilitate a multi-agent discussion around a topic."""

    def __init__(self, agents: list[ConversationAgent], max_rounds: int = 6) -> None:
        self._agents = agents
        self.max_rounds = max_rounds
        self.history: list[Message] = []

    def initiate_chat(self, topic: str, initiator: str | None = None) -> list[Message]:
        """Run a round-robin discussion on *topic*."""
        starter = initiator or self._agents[0].name
        self.history = [Message(sender=starter, content=topic)]

        for _round in range(self.max_rounds):
            for agent in self._agents:
                if not self.history:
                    break
                last = self.history[-1]
                if last.sender == agent.name:
                    continue
                reply = agent.receive(last, self.history)
                if reply is not None:
                    self.history.append(reply)
        return self.history


class HumanProxy(Agent):
    """An agent that yields control, expecting a human to supply the reply."""

    def __init__(self, name: str = "Human", role: str = "human") -> None:
        super().__init__(name=name, role=role)

    def request_input(self, prompt: str) -> str:
        """Signal that human input is needed (stub for external binding)."""
        return f"[{self.name} requires human input for: {prompt[:60]}...]"

    def send(self, content: str) -> Message:
        return Message(sender=self.name, content=content)
