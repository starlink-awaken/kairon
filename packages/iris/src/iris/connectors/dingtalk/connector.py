"""DingTalk connector — 通过 Webhook 发送消息通知"""

import json
import os
import urllib.request
from typing import Any, cast


class DingTalkConnector:
    name = "dingtalk"
    display_name = "DingTalk"

    def connect(self) -> dict:
        return {"connected": bool(os.environ.get("DINGTALK_WEBHOOK_URL"))}

    def send(self, message: str) -> dict:
        url = os.environ.get("DINGTALK_WEBHOOK_URL", "")
        if not url:
            return {"error": "DINGTALK_WEBHOOK_URL not set"}
        data = json.dumps({"msgtype": "text", "text": {"content": message[:2000]}}).encode()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                return cast("dict[Any, Any]", json.loads(r.read()))
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def sync(self) -> dict:
        return {"synced": True}
