"""KEMS Runtime — methodology operationalization (四平面+三链+三协议)."""


class Planes:
    KNOWLEDGE = "knowledge"
    EXPERIENCE = "experience"
    METHODOLOGY = "methodology"
    SYSTEM = "system"

    def __init__(self):
        self.MAP = {
            self.KNOWLEDGE: "KOS index (knowledge entities, relations, provenance)",
            self.EXPERIENCE: "gbrain memory (experience patterns, cases, lessons)",
            self.METHODOLOGY: "ontoderive (derivation rules, methodology stages)",
            self.SYSTEM: "ecos (health monitoring, entropy, alerts)",
        }


class Chains:
    DATA = "data"
    METHOD = "method"
    EVOLUTION = "evolution"

    def __init__(self):
        self.MAP = {
            self.DATA: "kronos -> eidos -> KOS",
            self.METHOD: "minerva -> ontoderive -> KOS",
            self.EVOLUTION: "KOS self (observe -> hypothesize -> experiment -> learn)",
        }


class Protocols:
    KNOWLEDGE = "knowledge"
    PROCESS = "process"
    EVOLUTION = "evolution"

    def __init__(self):
        self.MAP = {
            self.KNOWLEDGE: "eidos schema + validation rules",
            self.PROCESS: "pipeline:json workflow definitions",
            self.EVOLUTION: "KOS self adaptation rules + HITL gates",
        }


class KemsRuntime:
    def __init__(self):
        self.planes = Planes()
        self.chains = Chains()
        self.protocols = Protocols()

    def describe(self) -> dict:
        return {"planes": dict(self.planes.MAP), "chains": dict(self.chains.MAP), "protocols": dict(self.protocols.MAP)}
