"""Eidos Agent — NL interface for ontology modeling."""

from __future__ import annotations

import re
import subprocess
import sys


def parse_command(text: str) -> list[list[str]]:
    tl = text.lower()
    cmds = []
    if any(w in tl for w in ["define", "schema", "create"]):
        m = re.search(r"(?:called|named|for)\s+(\w+)", text, re.I)
        name = m.group(1) if m else "FromText"
        mt = "fact" if "fact" in tl else "domain" if "entity" in tl else "document"
        cmds.append(["eidos", "define", name, "--meta-type", mt])
    if any(w in tl for w in ["validate", "check"]):
        cmds.append(["eidos", "validate", "--all"])
    if any(w in tl for w in ["list", "show"]):
        cmds.append(["eidos", "list"])
    if not cmds:
        cmds.append(["eidos", "--help"])
    return cmds


def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("> ")
    cmds = parse_command(text)
    print(f"Interpreted: {text}")
    for c in cmds:
        print(f"  → {' '.join(c)}")
    if input("Execute? [Y/n] ").lower() in ("", "y"):
        for c in cmds:
            r = subprocess.run([sys.executable, "-m", "eidos.cli"] + c[1:], capture_output=True, text=True)
            print(r.stdout[:300])


if __name__ == "__main__":
    main()
