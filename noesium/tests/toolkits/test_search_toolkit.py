"""
Tests for JinaResearchToolkit functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noesium.core.toolify import ToolkitConfig, get_toolkit


@pytest.fixture
def jina_config():
    """Create a test configuration for JinaResearchToolkit."""
    return ToolkitConfig(name="jina_research", config={"JINA_API_KEY": "test_jina_key"})


@pytest.fixture
def jina_toolkit(jina_config):
    """Create JinaResearchToolkit instance for testing."""
    try:
        return get_toolkit("jina_research", jina_config)
    except KeyError as e:
        if "jina_research" in str(e):
            pytest.skip("JinaResearchToolkit not available for testing")
        raise


class TestJinaResearchToolkit:
    """Test cases for JinaResearchToolkit."""

    @pytest.mark.asyncio
    async def test_toolkit_initialization(self, jina_toolkit):
        """Test that JinaResearchToolkit initializes correctly."""
        assert jina_toolkit is not None
        assert hasattr(jina_toolkit, "get_web_content")
        assert hasattr(jina_toolkit, "web_qa")

    @pytest.mark.asyncio
    async def test_get_tools_map(self, jina_toolkit):
        """Test that tools map is correctly defined."""
        tools_map = await jina_toolkit.get_tools_map()

        expected_tools = ["get_web_content", "web_qa"]
        for tool_name in expected_tools:
            assert tool_name in tools_map
            assert callable(tools_map[tool_name])

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_web_content_success(self, mock_get, jina_toolkit):
        """Test successful content extraction."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="# Test Content\n\nThis is test content.")
        # raise_for_status is a sync method, use MagicMock not AsyncMock
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value.__aenter__.return_value = mock_response

        result = await jina_toolkit.get_web_content("https://example.com")

        assert isinstance(result, str)
        assert "Test Content" in result

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_get_web_content_error(self, mock_get, jina_toolkit):
        """Test content extraction error handling."""
        mock_get.side_effect = Exception("Connection failed")

        result = await jina_toolkit.get_web_content("https://example.com")

        assert isinstance(result, str)
        assert "Error" in result

    @pytest.mark.asyncio
    @patch("noesium.toolkits.jina_research_toolkit.JinaResearchToolkit.get_web_content")
    @patch("noesium.toolkits.jina_research_toolkit.JinaResearchToolkit.llm_client")
    async def test_web_qa_with_question(self, mock_llm, mock_get_web_content, jina_toolkit):
        """Test web Q&A with a specific question."""
        mock_get_web_content.return_value = "This is test content about Python programming."
        mock_llm.completion.return_value = "Python is a programming language."

        result = await jina_toolkit.web_qa("https://example.com", "What is Python?")

        assert isinstance(result, str)
        mock_get_web_content.assert_called_once_with("https://example.com")
        assert mock_llm.completion.call_count == 2

    @pytest.mark.asyncio
    @patch("noesium.toolkits.jina_research_toolkit.JinaResearchToolkit.get_web_content")
    @patch("noesium.toolkits.jina_research_toolkit.JinaResearchToolkit.llm_client")
    async def test_web_qa_summary(self, mock_llm, mock_get_web_content, jina_toolkit):
        """Test web Q&A for content summary."""
        mock_get_web_content.return_value = "This is test content."
        mock_llm.completion.return_value = "Summary of the content."

        result = await jina_toolkit.web_qa("https://example.com", "Summarize this content")

        assert isinstance(result, str)
        mock_get_web_content.assert_called_once_with("https://example.com")
        assert mock_llm.completion.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_url_handling(self, jina_toolkit):
        """Test handling of invalid URLs."""
        result = await jina_toolkit.get_web_content("not-a-url")

        assert isinstance(result, str)
        assert "Error" in result or "Invalid" in result


class TestJinaResearchToolkitIntegration:
    """Integration tests for JinaResearchToolkit (require API keys)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_real_content_extraction(self):
        """Test with real content extraction (requires API key)."""
        config = ToolkitConfig(name="jina_research", config={"JINA_API_KEY": "your_real_jina_key"})
        toolkit = get_toolkit("jina_research", config)

        result = await toolkit.get_web_content("https://docs.python.org/3/")

        if isinstance(result, str) and (
            "error" in result.lower() or "forbidden" in result.lower() or "unauthorized" in result.lower()
        ):
            pytest.skip("Valid API key required for this test")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Python" in result
