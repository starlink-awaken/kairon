"""CLI entry point for sharedbrain-bridge."""

import json
import sys

from sot_bridge.sharedbrain_bridge.eu import EUBridge
from sot_bridge.sharedbrain_bridge.immune import ImmuneBridge
from sot_bridge.sharedbrain_bridge.sync import SyncBridge


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        sb = SyncBridge()
        organs = sb.get_active_organs()
        print(f"Active organs: {len(organs)}")
        for o in organs:
            print(f"  {o['name']}: {o['status']}")
    elif cmd == "sync":
        sb = SyncBridge()
        result = sb.batch_sync_to_memory()
        print(json.dumps(result, indent=2))
    elif cmd == "eu":
        eb = EUBridge()
        caller = sys.argv[2] if len(sys.argv) > 2 else "kairon"
        print(json.dumps(eb.check_balance(caller), indent=2))
    elif cmd == "audit":
        ib = ImmuneBridge()
        content = " ".join(sys.argv[2:]) or "test content"
        print(json.dumps(ib.audit(content), indent=2))
    else:
        print("Usage: sb-bridge <status|sync|eu|audit>")


if __name__ == "__main__":
    main()
