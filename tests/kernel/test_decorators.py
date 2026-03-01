"""Tests for @kernel_node decorator."""

import pytest

from noesium.core.kernel.decorators import kernel_node


class TestKernelNodeDecorator:
    def test_attaches_metadata(self):
        @kernel_node(deterministic=True)
        def my_node(state):
            return state

        assert hasattr(my_node, "_kernel_meta")
        assert my_node._kernel_meta["deterministic"] is True
        assert my_node._kernel_meta["entropy_sources"] == []

    def test_custom_entropy_sources(self):
        @kernel_node(deterministic=False, entropy_sources=["llm", "network"])
        def my_node(state):
            return state

        assert my_node._kernel_meta["deterministic"] is False
        assert my_node._kernel_meta["entropy_sources"] == ["llm", "network"]

    def test_preserves_sync_function_name(self):
        @kernel_node(deterministic=True)
        def compute_stuff(state):
            return state

        assert compute_stuff.__name__ == "compute_stuff"

    def test_preserves_async_function_name(self):
        @kernel_node(deterministic=False)
        async def fetch_data(state):
            return state

        assert fetch_data.__name__ == "fetch_data"

    def test_sync_function_callable(self):
        @kernel_node(deterministic=True)
        def add_one(state):
            return {"count": state.get("count", 0) + 1}

        result = add_one({"count": 5})
        assert result == {"count": 6}

    @pytest.mark.asyncio
    async def test_async_function_callable(self):
        @kernel_node(deterministic=False, entropy_sources=["llm"])
        async def generate(state):
            return {"output": "hello"}

        result = await generate({})
        assert result == {"output": "hello"}

    def test_default_values(self):
        @kernel_node()
        def node(state):
            return state

        assert node._kernel_meta["deterministic"] is True
        assert node._kernel_meta["entropy_sources"] == []
