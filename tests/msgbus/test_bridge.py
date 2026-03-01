"""Tests for EnvelopeBridge and EnvelopeEvent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from noesium.core.event.envelope import AgentRef, EventEnvelope, TraceContext
from noesium.core.event.store import InMemoryEventStore
from noesium.core.msgbus.bridge import EnvelopeBridge, EnvelopeEvent


def _make_envelope(event_type: str = "test.event") -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        producer=AgentRef(agent_id="a1", agent_type="test"),
        trace=TraceContext(),
        payload={"data": event_type},
    )


class TestEnvelopeEvent:
    def test_wraps_envelope(self):
        env = _make_envelope()
        event = EnvelopeEvent(envelope=env)
        assert event.envelope is env
        assert event.data is env


class TestEnvelopeBridgeUnit:
    """Unit tests using mocked EventBus to avoid bubus async runtime."""

    @pytest.fixture()
    def store(self):
        return InMemoryEventStore()

    @pytest.fixture()
    def bus(self):
        bus = MagicMock()
        bus.on = MagicMock()
        bus.dispatch = MagicMock()
        return bus

    @pytest.fixture()
    def bridge(self, store, bus):
        return EnvelopeBridge(event_store=store, event_bus=bus)

    @pytest.mark.asyncio
    async def test_publish_stores_event(self, bridge, store):
        env = _make_envelope()
        await bridge.publish(env)
        events = await store.read()
        assert len(events) == 1
        assert events[0].event_id == env.event_id

    @pytest.mark.asyncio
    async def test_publish_dispatches_on_bus(self, bridge, bus):
        env = _make_envelope()
        await bridge.publish(env)
        bus.dispatch.assert_called_once()
        dispatched_event = bus.dispatch.call_args[0][0]
        assert isinstance(dispatched_event, EnvelopeEvent)
        assert dispatched_event.envelope.event_id == env.event_id

    @pytest.mark.asyncio
    async def test_subscribe_filters_by_event_type(self, bridge):
        handler_a = AsyncMock()
        handler_a.__name__ = "handler_a"
        handler_b = AsyncMock()
        handler_b.__name__ = "handler_b"

        await bridge.subscribe("type.a", handler_a)
        await bridge.subscribe("type.b", handler_b)

        env_a = _make_envelope("type.a")
        await bridge._dispatch(EnvelopeEvent(envelope=env_a))

        handler_a.assert_awaited_once()
        handler_b.assert_not_awaited()
        received = handler_a.call_args[0][0]
        assert received.event_type == "type.a"

    @pytest.mark.asyncio
    async def test_multiple_handlers_same_type(self, bridge):
        h1 = AsyncMock()
        h1.__name__ = "h1"
        h2 = AsyncMock()
        h2.__name__ = "h2"

        await bridge.subscribe("x", h1)
        await bridge.subscribe("x", h2)
        await bridge._dispatch(EnvelopeEvent(envelope=_make_envelope("x")))

        h1.assert_awaited_once()
        h2.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_error_does_not_break_others(self, bridge):
        failing = AsyncMock(side_effect=RuntimeError("boom"))
        failing.__name__ = "failing"
        succeeding = AsyncMock()
        succeeding.__name__ = "succeeding"

        await bridge.subscribe("x", failing)
        await bridge.subscribe("x", succeeding)
        await bridge._dispatch(EnvelopeEvent(envelope=_make_envelope("x")))

        succeeding.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_handlers_for_type(self, bridge):
        await bridge._dispatch(EnvelopeEvent(envelope=_make_envelope("unhandled")))
