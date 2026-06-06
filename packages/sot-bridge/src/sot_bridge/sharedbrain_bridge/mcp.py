from fastmcp import FastMCP

mcp = FastMCP("sot-bridge-persona", mask_error_details=True)

FORMAT_VERSION = "persona-v1"

PERSONAS = {
    "builder": "You are @Builder. You are the engineering brain. You focus on 'How' and MVP. You prioritize high efficiency and modularity.",
    "devil": "You are @Devil. You are the critical thinker. You focus on 'Risk' and ROI. You challenge assumptions and prevent fragility.",
    "sage": "You are @Sage. You are the system thinker. You focus on 'Context' and 'Essence'. You ensure long-term architectural integrity.",
}


@mcp.resource("bos://persona/{role}")
def read_persona(role: str) -> str:
    """Get the System Prompt for a specific persona role."""
    role = role.lower()
    if role not in PERSONAS:
        return f"Unknown persona: {role}. Available: {list(PERSONAS.keys())}"
    return PERSONAS[role]


def main():
    mcp.run()


if __name__ == "__main__":
    main()
