"""Tests for memory — WorkingMemory (TTL-based) and ProjectMemory/OrgMemory (SQLite)."""

import time

from agent_runtime.memory import MemoryEntry, WorkingMemory


class TestMemoryEntry:
    """MemoryEntry dataclass defaults."""

    def test_default_ttl(self):
        entry = MemoryEntry(key="k", value="v")
        assert entry.ttl_seconds == 3600.0
        assert entry.access_count == 0

    def test_custom_ttl(self):
        entry = MemoryEntry(key="k", value="v", ttl_seconds=10.0)
        assert entry.ttl_seconds == 10.0


class TestWorkingMemory:
    """WorkingMemory TTL-based store."""

    def test_set_and_get(self):
        wm = WorkingMemory()
        wm.set("greeting", "hello")
        assert wm.get("greeting") == "hello"

    def test_get_missing_key(self):
        wm = WorkingMemory()
        assert wm.get("nonexistent") is None

    def test_get_expired_entry(self):
        wm = WorkingMemory(default_ttl=0.01)
        wm.set("ephemeral", "data", ttl_seconds=0.01)
        time.sleep(0.02)
        assert wm.get("ephemeral") is None

    def test_entry_access_updates_position(self):
        wm = WorkingMemory(max_entries=2)
        wm.set("a", 1)
        wm.set("b", 2)
        wm.get("a")  # accesses 'a' again
        wm.set("c", 3)  # should evict 'b' (LRU) not 'a'
        assert wm.get("a") == 1
        assert wm.get("b") is None
        assert wm.get("c") == 3

    def test_eviction_when_full(self):
        wm = WorkingMemory(max_entries=3)
        wm.set("x", 10)
        wm.set("y", 20)
        wm.set("z", 30)
        wm.set("w", 40)  # evicts 'x'
        assert wm.get("x") is None
        assert wm.get("w") == 40

    def test_cleanup_returns_expired_count(self):
        wm = WorkingMemory(default_ttl=0.01)
        wm.set("a", 1, ttl_seconds=0.01)
        wm.set("b", 2, ttl_seconds=0.01)
        wm.set("c", 3, ttl_seconds=600)  # long-lived
        time.sleep(0.02)
        removed = wm.cleanup()
        assert removed == 2
        assert wm.get("a") is None
        assert wm.get("c") == 3

    def test_clear(self):
        wm = WorkingMemory()
        wm.set("a", 1)
        wm.set("b", 2)
        wm.clear()
        assert wm.get("a") is None
        assert wm.get("b") is None

    def test_cleanup_when_nothing_expired(self):
        wm = WorkingMemory(default_ttl=600)
        wm.set("a", 1)
        assert wm.cleanup() == 0

    def test_multiple_entries(self):
        wm = WorkingMemory()
        wm.set("a", 10)
        wm.set("b", "hello")
        wm.set("c", [1, 2, 3])
        assert wm.get("a") == 10
        assert wm.get("b") == "hello"
        assert wm.get("c") == [1, 2, 3]
