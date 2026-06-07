import json
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel

from .detection import detect_backends
from .provider import LLMRequest, ToolSchema

mcp = FastMCP("llm-gateway")


class GenerateRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None


@mcp.tool()
async def llm_generate(req: GenerateRequest) -> str:
    """Generate LLM response using the unified gateway with full schema support."""
    providers = detect_backends()
    if not providers:
        return json.dumps({"error": "No LLM backend available."})

    provider = providers[0]

    # Convert tools
    mapped_tools = None
    if req.tools:
        mapped_tools = []
        for t in req.tools:
            if "function" in t:
                f = t["function"]
                mapped_tools.append(
                    ToolSchema(name=f["name"], description=f.get("description", ""), parameters=f.get("parameters", {}))
                )

    llm_req = LLMRequest(model=req.model or provider.default_model, messages=req.messages, tools=mapped_tools)

    try:
        resp = await provider.generate(llm_req)

        # Format response back to OpenAI style
        result = {"role": "assistant", "content": resp.content, "tool_calls": [], "finish_reason": "stop"}

        if resp.tool_calls:
            result["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                for tc in resp.tool_calls
            ]
            result["finish_reason"] = "tool_calls"

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def main():
    mcp.run()


if __name__ == "__main__":
    main()
