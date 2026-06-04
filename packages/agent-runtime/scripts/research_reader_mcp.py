#!/usr/bin/env python3
"""Research Reader MCP Server -- Phase A: read-only operations.

Usage:
  python3 research_reader_mcp.py              # Run as MCP server (stdio)
  python3 research_reader_mcp.py --call <tool> <json_args>  # Direct call mode
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".workspace" / "data.db"


def _query(sql, params=()):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _direct_call(tool, args):
    if tool == "research_list":
        limit = args.get("limit", 10)
        rows = _query(
            "SELECT id, topic, created_at, source_count, summary, archived_at FROM research WHERE quarantined_at IS NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        return json.dumps(rows, ensure_ascii=False, default=str)
    elif tool == "research_get":
        rows = _query("SELECT * FROM research WHERE id = ?", (args["id"],))
        if not rows:
            return json.dumps(None)
        row = rows[0]
        fups = _query(
            "SELECT question, answer, timestamp FROM follow_ups WHERE research_id = ? ORDER BY timestamp", (args["id"],)
        )
        row["follow_ups"] = fups
        return json.dumps(row, ensure_ascii=False, default=str)
    elif tool == "research_dossier":
        record = _query(
            "SELECT id, topic, created_at, summary, source_count, archived_at FROM research WHERE id = ?", (args["id"],)
        )
        if not record:
            return json.dumps(None)
        parents = _query(
            "SELECT r.id, r.topic, r.created_at FROM research_relations rr JOIN research r ON r.id = rr.parent_id WHERE rr.child_id = ?",
            (args["id"],),
        )
        children = _query(
            "SELECT r.id, r.topic, r.created_at FROM research_relations rr JOIN research r ON r.id = rr.child_id WHERE rr.parent_id = ?",
            (args["id"],),
        )
        pubs = _query(
            "SELECT style, published_at, output_path FROM publications WHERE research_id = ? ORDER BY published_at",
            (args["id"],),
        )
        return json.dumps(
            {"record": record[0], "parents": parents, "children": children, "publications": pubs},
            ensure_ascii=False,
            default=str,
        )
    elif tool == "research_timeline":
        events = _query(
            "SELECT event_type, description, created_at FROM research_timeline WHERE research_id = ? ORDER BY created_at",
            (args["id"],),
        )
        return json.dumps(events, ensure_ascii=False, default=str)
    return json.dumps({"error": f"Unknown tool: {tool}"})


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--call":
        tool = sys.argv[2]
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(_direct_call(tool, args))
        return

    from mcp.server import Server, stdio_server

    server = Server("workspace-reader")

    @server.list_tools()
    async def list_tools():
        return [
            {
                "name": "research_list",
                "description": "List research records",
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}},
            },
            {
                "name": "research_get",
                "description": "Get research detail",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
            {
                "name": "research_dossier",
                "description": "Get research relations",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
            {
                "name": "research_timeline",
                "description": "Get research timeline",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
            },
        ]

    @server.call_tool()
    async def call_tool(name, args):
        return [{"type": "text", "text": _direct_call(name, args)}]

    async def run():
        async with stdio_server(server):
            await server.run()

    asyncio.run(run())


if __name__ == "__main__":
    main()
