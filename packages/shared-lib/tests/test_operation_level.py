"""Tests for kairon_lib operation_level module."""

import pytest
from kairon_lib.operation_level import OpLevel, check_operation_level, operation_level


class TestOpLevel:
    def test_values(self):
        assert OpLevel.READ == 0
        assert OpLevel.LOW_RISK == 1
        assert OpLevel.HIGH_RISK == 2
        assert OpLevel.DESTRUCTIVE == 3

    def test_ordering(self):
        assert OpLevel.READ < OpLevel.HIGH_RISK
        assert OpLevel.DESTRUCTIVE > OpLevel.LOW_RISK


class TestCheckOperationLevel:
    def test_l0_allowed(self):
        check_operation_level(OpLevel.READ, "read_tool", {"arg": 1})

    def test_l1_allowed(self):
        check_operation_level(OpLevel.LOW_RISK, "low_risk_tool", {"arg": 1})

    def test_l2_rejects_without_confirmation(self):
        with pytest.raises(PermissionError, match="L2"):
            check_operation_level(OpLevel.HIGH_RISK, "delete_tool", {})

    def test_l2_allows_with_confirmation(self):
        check_operation_level(OpLevel.HIGH_RISK, "delete_tool", {"_confirmed": True})

    def test_l3_rejects_without_cooldown(self):
        with pytest.raises(PermissionError, match="L3"):
            check_operation_level(OpLevel.DESTRUCTIVE, "nuke_tool", {"_confirmed": True})

    def test_l3_allows_with_full_approval(self):
        check_operation_level(OpLevel.DESTRUCTIVE, "nuke_tool", {"_confirmed": True, "_cool_down_hours": 24})


class TestOperationLevelDecorator:
    def test_decorator_returns_callable(self):
        @operation_level(OpLevel.READ)
        def read_fn():
            return "ok"

        assert callable(read_fn)
        assert read_fn() == "ok"

    def test_decorator_preserves_metadata(self):
        @operation_level(OpLevel.HIGH_RISK, human_approval=True)
        def risky_fn():
            pass

        assert risky_fn._operation_level == 2
        assert risky_fn._human_approval is True

    def test_decorator_rejects_l2_without_confirm(self):
        @operation_level(OpLevel.HIGH_RISK)
        def delete_me():
            return "deleted"

        with pytest.raises(PermissionError):
            delete_me()
