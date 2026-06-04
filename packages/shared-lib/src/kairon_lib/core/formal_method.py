from __future__ import annotations

"""Formal method specification generator (TLA+ / Alloy).

Migrated from agentmesh/packages/toolkit/src/architecture/FormalMethod.ts.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FormalMethodType(Enum):
    TLA_PLUS = "tla+"
    ALLOY = "alloy"


class State:
    def __init__(self, name: str, invariant: str | None = None, action: str | None = None) -> None:
        self.name = name
        self.invariant = invariant
        self.action = action


@dataclass
class Transition:
    from_state: str
    to_state: str
    action: str = ""
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)


@dataclass
class Invariant:
    name: str
    expression: str
    description: str | None = None


@dataclass
class Property:
    name: str
    type: str
    expression: str
    description: str | None = None


class FormalMethod:
    """TLA+ or Alloy formal specification generator."""

    def __init__(self, method_type: FormalMethodType = FormalMethodType.TLA_PLUS) -> None:
        self._type = method_type
        self._module_name = "FormalModel"
        self._variables: dict[str, str] = {}
        self._constants: dict[str, str] = {}
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._invariants: list[Invariant] = []
        self._properties: list[Property] = []

    def set_module_name(self, name: str) -> FormalMethod:
        self._module_name = name
        return self

    def add_variable(self, name: str, type_: str) -> FormalMethod:
        self._variables[name] = type_
        return self

    def add_constant(self, name: str, value: str) -> FormalMethod:
        self._constants[name] = value
        return self

    def add_state(self, name: str, invariant: str | None = None) -> FormalMethod:
        self._states[name] = State(name, invariant)
        return self

    def add_transition(
        self, from_state: str, to_state: str, action: str = "",
        preconditions: list[str] | None = None, postconditions: list[str] | None = None,
    ) -> FormalMethod:
        if from_state not in self._states:
            self.add_state(from_state)
        if to_state not in self._states:
            self.add_state(to_state)
        self._transitions.append(Transition(from_state, to_state, action, preconditions or [], postconditions or []))
        return self

    def add_invariant(self, name: str, expression: str, description: str | None = None) -> FormalMethod:
        self._invariants.append(Invariant(name, expression, description))
        return self

    def add_property(self, name: str, type_: str, expression: str, description: str | None = None) -> FormalMethod:
        self._properties.append(Property(name, type_, expression, description))
        return self

    def verify(self) -> dict[str, Any]:
        errors: list[str] = []
        for t in self._transitions:
            if t.from_state not in self._states:
                errors.append(f"State not found: {t.from_state}")
            if t.to_state not in self._states:
                errors.append(f"State not found: {t.to_state}")
        return {
            "success": len(errors) == 0,
            "errors": errors,
            "warnings": [] if self._states else ["No states defined"],
        }

    def generate(self) -> str:
        if self._type == FormalMethodType.ALLOY:
            return f"module {self._module_name}\n\nrun {{}} for 5"
        return self._to_tla_plus()

    def _to_tla_plus(self) -> str:
        lines = [f"---- MODULE {self._module_name} ----", "", "EXTENDS Naturals, Sequences", ""]
        if self._constants:
            lines.append("CONSTANTS")
            for name, value in self._constants.items():
                lines.append(f"  {name} = {value}")
            lines.append("")
        if self._variables:
            lines.append("VARIABLES")
            lines.append("  " + ", ".join(self._variables.keys()))
            lines.append("")
        if self._states:
            lines.append("State == {" + ", ".join(self._states.keys()) + "}")
            lines.append("")
        if self._transitions:
            lines.append("(* Actions *)")
            for t in self._transitions:
                action_name = re.sub(r"\s+", "", t.action or "transition")
                lines.append(f"{action_name} ==")
                lines.append("  TRUE")
                lines.append("")
        for inv in self._invariants:
            lines.append(f"(* @{inv.name}: {inv.expression} *)")
        for prop in self._properties:
            lines.append(f"THEOREM {prop.name} == {prop.expression}")
        lines.append("")
        lines.append("====")
        return "\n".join(lines)
