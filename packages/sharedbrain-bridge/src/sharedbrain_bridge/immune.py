"""Immune Audit Bridge — kairon knowledge → SharedBrain D-Immunity."""

import json
import logging
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)
DEFAULT_SB = "http://localhost:7421"


class ImmuneBridge:
    def __init__(self, sharedbrain=DEFAULT_SB):
        self.sb = sharedbrain

    def audit(self, content: str, title: str = "", source: str = "") -> dict:
        try:
            payload = json.dumps({"content": content, "title": title, "source": source}).encode()
            req = Request(f"{self.sb}/api/v1/immunity/audit", data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=10)
            return json.loads(resp.read().decode())
        except Exception as e:
            return {"risk": "UNKNOWN", "error": str(e)}
