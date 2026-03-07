"""Tests for LLM warm-up functionality."""

import time
from unittest.mock import MagicMock, patch

import pytest
from noeagent.agent import NoeAgent
from noeagent.config import NoeConfig


@pytest.fixture
def mock_llm():
    """Create a mock LLM client (sync completion, as in real LLM clients)."""
    llm = MagicMock()
    llm.completion = MagicMock(return_value="Ready response")
    return llm


@pytest.fixture
def mock_llm_slow():
    """Create a mock LLM client that blocks longer than the timeout."""
    llm = MagicMock()

    def slow_completion(*args, **kwargs):
        time.sleep(35)  # Longer than default timeout; runs in thread
        return "Ready response"

    llm.completion = slow_completion
    return llm


@pytest.fixture
def mock_llm_error():
    """Create a mock LLM client that raises an error."""
    llm = MagicMock()
    llm.completion = MagicMock(side_effect=Exception("Connection failed"))
    return llm


class TestLLMWarmup:
    """Test LLM warm-up functionality."""

    @pytest.mark.asyncio
    async def test_warmup_enabled_by_default(self, mock_llm):
        """Test that warm-up is enabled by default."""
        config = NoeConfig()
        assert config.llm_warmup_on_init is True
        assert config.llm_warmup_timeout == 30

    @pytest.mark.asyncio
    async def test_warmup_called_during_initialization(self, mock_llm):
        """Test that warm-up is called during agent initialization."""
        config = NoeConfig(
            llm_provider="openai",
            mode="agent",
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm):
            agent = NoeAgent(config)
            await agent.initialize()

            # Verify warm-up was called
            mock_llm.completion.assert_called_once()
            call_args = mock_llm.completion.call_args
            assert call_args[0][0][0]["role"] == "user"
            assert call_args[0][0][0]["content"] == "Ready"

    @pytest.mark.asyncio
    async def test_warmup_can_be_disabled(self, mock_llm):
        """Test that warm-up can be disabled via config."""
        config = NoeConfig(
            llm_provider="openai",
            mode="agent",
            llm_warmup_on_init=False,
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm):
            agent = NoeAgent(config)
            await agent.initialize()

            # Verify warm-up was NOT called
            mock_llm.completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_warmup_timeout_handled_gracefully(self, mock_llm_slow):
        """Test that warm-up timeout doesn't crash initialization."""
        config = NoeConfig(
            llm_provider="openai",
            mode="agent",
            llm_warmup_timeout=5,  # 5 second timeout
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm_slow):
            agent = NoeAgent(config)

            # Should not raise exception
            await agent.initialize()
            assert agent._initialized is True

    @pytest.mark.asyncio
    async def test_warmup_error_handled_gracefully(self, mock_llm_error):
        """Test that warm-up errors don't crash initialization."""
        config = NoeConfig(
            llm_provider="openai",
            mode="agent",
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm_error):
            agent = NoeAgent(config)

            # Should not raise exception
            await agent.initialize()
            assert agent._initialized is True

    @pytest.mark.asyncio
    async def test_warmup_not_called_in_ask_mode(self, mock_llm):
        """Test that warm-up is skipped in ask mode."""
        config = NoeConfig(
            llm_provider="openai",
            mode="ask",
            llm_warmup_on_init=True,  # Even when enabled
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm):
            agent = NoeAgent(config)
            await agent.initialize()

            # Verify warm-up was NOT called in ask mode
            mock_llm.completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_warmup_custom_timeout(self, mock_llm):
        """Test that custom timeout is respected."""
        config = NoeConfig(
            llm_provider="openai",
            mode="agent",
            llm_warmup_timeout=60,  # Custom timeout
        )

        with patch("noesium.core.agent.base.get_llm_client", return_value=mock_llm):
            agent = NoeAgent(config)
            assert agent.config.llm_warmup_timeout == 60
