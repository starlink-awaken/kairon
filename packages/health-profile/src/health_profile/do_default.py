"""P58-W0 health_profile do_default — 真业务 (调 health_profile models 真类)."""
from __future__ import annotations

from typing import Any


def do_default(args: dict[str, Any]) -> dict[str, Any]:
    """P58-W0 health_profile do_default: 真调 HealthCheckRecord / HealthProfile / BloodType."""
    try:
        from health_profile import (
            BloodType,
            HealthCheckRecord,
            HealthProfile,
            VaccinationRecord,
        )
    except Exception as exc:
        return {"_method": "do_default", "_error": f"import: {type(exc).__name__}: {exc}"}

    action = args.get("action", "schema")
    try:
        if action == "schema":
            return {
                "_method": "do_default", "_action": "schema",
                "BloodType_values": [bt.value for bt in BloodType],
                "HealthCheckRecord_fields": list(HealthCheckRecord.__dataclass_fields__.keys()),
                "HealthProfile_fields": list(HealthProfile.__dataclass_fields__.keys()),
                "VaccinationRecord_fields": list(VaccinationRecord.__dataclass_fields__.keys()),
            }
        if action == "blood_types":
            return {
                "_method": "do_default", "_action": "blood_types",
                "types": [bt.value for bt in BloodType],
            }
        return {"_method": "do_default", "_error": f"unknown action: {action}"}
    except Exception as exc:
        return {"_method": "do_default", "_action": action, "_error": f"{type(exc).__name__}: {exc}"}


__all__ = ["do_default"]
