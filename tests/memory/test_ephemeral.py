"""Tests for EphemeralMemory."""

from noesium.core.memory.ephemeral import EphemeralMemory


class TestEphemeralMemory:
    def test_get_set(self):
        mem = EphemeralMemory()
        mem.set("key", "value")
        assert mem.get("key") == "value"

    def test_get_missing_returns_default(self):
        mem = EphemeralMemory()
        assert mem.get("missing") is None
        assert mem.get("missing", 42) == 42

    def test_delete_existing(self):
        mem = EphemeralMemory()
        mem.set("k", 1)
        assert mem.delete("k") is True
        assert mem.get("k") is None

    def test_delete_missing(self):
        mem = EphemeralMemory()
        assert mem.delete("nope") is False

    def test_clear(self):
        mem = EphemeralMemory()
        mem.set("a", 1)
        mem.set("b", 2)
        mem.clear()
        assert mem.keys() == []

    def test_keys(self):
        mem = EphemeralMemory()
        mem.set("x", 10)
        mem.set("y", 20)
        assert sorted(mem.keys()) == ["x", "y"]

    def test_overwrite(self):
        mem = EphemeralMemory()
        mem.set("k", "old")
        mem.set("k", "new")
        assert mem.get("k") == "new"
