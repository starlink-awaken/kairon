"""Feishu(Lark) connector — 通过 Webhook 发送消息"""

import json
import os
import urllib.request


class FeishuConnector:
    name = "feishu"
    display_name = "Feishu (Lark)"

    def connect(self) -> dict:
        return {"connected": bool(os.environ.get("FEISHU_WEBHOOK_URL"))}

    def send(self, message: str) -> dict:
        url = os.environ.get("FEISHU_WEBHOOK_URL", "")
        if not url:
            return {"error": "FEISHU_WEBHOOK_URL not set"}
        data = json.dumps({"msg_type": "text", "content": {"text": message[:2000]}}).encode()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"sent": True}
        except Exception as e:
            return {"error": str(e)}

    def sync(self) -> dict:
        return {"synced": True}
