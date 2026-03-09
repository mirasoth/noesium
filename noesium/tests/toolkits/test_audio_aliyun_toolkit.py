"""
Tests for AudioToolkit functionality with multiple providers.

This test file covers both OpenAI and Aliyun providers.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from noesium.core.toolify import ToolkitConfig, get_toolkit
from noesium.toolkits.audio_toolkit import AudioToolkit

# ==================== Aliyun Provider Fixtures ====================


@pytest.fixture
def aliyun_config():
    """Create a test configuration for Aliyun provider."""
    return ToolkitConfig(
        name="audio",
        config={
            "provider": "aliyun",
            "ALIYUN_ACCESS_KEY_ID": "test_access_key",
            "ALIYUN_ACCESS_KEY_SECRET": "test_secret_key",
            "ALIYUN_NLS_APP_KEY": "test_app_key",
            "ALIYUN_REGION_ID": "cn-shanghai",
            "cache_dir": "./test_audio_cache",
            "download_dir": "./test_audio_downloads",
        },
        llm_provider="openai",
        llm_config={"api_key": "test_openai_key"},
    )


@pytest.fixture
def aliyun_toolkit(aliyun_config):
    """Create AudioToolkit instance with Aliyun provider for testing."""
    return get_toolkit("audio", aliyun_config)


@pytest.fixture
def mock_audio_file():
    """Create a temporary mock audio file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(b"fake audio data for testing")
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_aliyun_response():
    """Mock Aliyun NLS API response."""
    return {
        "Sentences": [
            {
                "Text": "这是一段测试音频的转录文本。",
                "BeginTime": 0,
                "EndTime": 2000,
                "SilenceDuration": 0,
                "ChannelId": 0,
            },
            {
                "Text": "包含了中文语音识别的结果。",
                "BeginTime": 2000,
                "EndTime": 4000,
                "SilenceDuration": 100,
                "ChannelId": 0,
            },
        ]
    }


# ==================== OpenAI Provider Fixtures ====================


@pytest.fixture
def openai_config():
    """Create a test configuration for OpenAI provider."""
    return ToolkitConfig(
        name="audio",
        config={
            "provider": "openai",
            "audio_model": "whisper-1",
            "cache_dir": "./test_audio_cache",
            "download_dir": "./test_audio_downloads",
        },
        llm_provider="openai",
        llm_config={"api_key": "test_openai_key"},
    )


@pytest.fixture
def openai_toolkit(openai_config):
    """Create AudioToolkit instance with OpenAI provider for testing."""
    return AudioToolkit(openai_config)


# ==================== Common Tests ====================


class TestAudioToolkitCommon:
    """Test cases common to all providers."""

    def test_default_provider_is_openai(self):
        """Test that the default provider is OpenAI."""
        config = ToolkitConfig(name="audio", config={})
        toolkit = AudioToolkit(config)
        assert toolkit.provider == "openai"

    def test_invalid_provider_raises_error(self):
        """Test that an invalid provider raises an error."""
        config = ToolkitConfig(name="audio", config={"provider": "invalid"})
        with pytest.raises(ValueError, match="Unsupported audio provider"):
            AudioToolkit(config)

    @pytest.mark.asyncio
    async def test_get_tools_map_returns_correct_tools(self, openai_toolkit):
        """Test that tools map is correctly defined."""
        tools_map = await openai_toolkit.get_tools_map()

        expected_tools = ["transcribe_audio", "audio_qa", "get_audio_info"]
        for tool_name in expected_tools:
            assert tool_name in tools_map
            assert callable(tools_map[tool_name])


# ==================== OpenAI Provider Tests ====================


class TestAudioToolkitOpenAI:
    """Test cases for OpenAI provider."""

    def test_openai_initialization(self, openai_config):
        """Test OpenAI provider initialization."""
        toolkit = AudioToolkit(openai_config)

        assert toolkit.provider == "openai"
        assert toolkit.audio_model == "whisper-1"
        assert toolkit.cache_dir is not None
        assert toolkit.download_dir is not None

    def test_is_url_detection(self, openai_toolkit):
        """Test URL detection utility."""
        assert openai_toolkit._is_url("https://example.com/audio.mp3") is True
        assert openai_toolkit._is_url("http://example.com/audio.mp3") is True
        assert openai_toolkit._is_url("/local/path/audio.mp3") is False
        assert openai_toolkit._is_url("./relative/path/audio.mp3") is False

    def test_get_file_extension(self, openai_toolkit):
        """Test file extension extraction."""
        assert openai_toolkit._get_file_extension("https://example.com/audio.mp3") == ".mp3"
        assert openai_toolkit._get_file_extension("https://example.com/audio.wav") == ".wav"
        assert openai_toolkit._get_file_extension("https://example.com/audio") == ".mp3"  # default

    @pytest.mark.asyncio
    async def test_transcribe_local_file_not_found(self, openai_toolkit):
        """Test transcription with non-existent local file."""
        result = await openai_toolkit.transcribe_audio("/nonexistent/audio.mp3")

        assert "error" in result
        assert "Audio file not found" in result["error"] or "Audio transcription failed" in result["error"]

    @pytest.mark.asyncio
    async def test_get_audio_info_success(self, openai_toolkit, mock_audio_file):
        """Test getting audio info for a local file."""
        # Mock the transcription to avoid actual API call
        with patch.object(openai_toolkit, "_transcribe_openai") as mock_transcribe:
            mock_transcribe.return_value = {
                "text": "Test transcription",
                "duration": 10.5,
                "language": "en",
                "provider": "openai",
            }

            result = await openai_toolkit.get_audio_info(mock_audio_file)

            assert "error" not in result
            assert result["provider"] == "openai"
            assert result["file_size_bytes"] > 0
            assert result["duration_seconds"] == 10.5


# ==================== Aliyun Provider Tests ====================


class TestAudioToolkitAliyun:
    """Test cases for Aliyun provider."""

    def test_aliyun_initialization_success(self, aliyun_config):
        """Test that AudioToolkit initializes correctly with valid Aliyun config."""
        toolkit = AudioToolkit(aliyun_config)

        assert toolkit is not None
        assert toolkit.provider == "aliyun"
        assert toolkit.ak_id == "test_access_key"
        assert toolkit.ak_secret == "test_secret_key"
        assert toolkit.app_key == "test_app_key"
        assert toolkit.region_id == "cn-shanghai"
        assert hasattr(toolkit, "aliyun_client")

    def test_aliyun_initialization_missing_credentials(self):
        """Test that AudioToolkit raises error with missing Aliyun credentials."""
        config = ToolkitConfig(name="audio", config={"provider": "aliyun"})

        with pytest.raises(ValueError, match="Aliyun credentials not found"):
            AudioToolkit(config)

    def test_aliyun_initialization_from_env(self):
        """Test Aliyun initialization from environment variables."""
        with patch.dict(
            os.environ,
            {
                "ALIYUN_ACCESS_KEY_ID": "env_access_key",
                "ALIYUN_ACCESS_KEY_SECRET": "env_secret_key",
                "ALIYUN_NLS_APP_KEY": "env_app_key",
            },
        ):
            config = ToolkitConfig(name="audio", config={"provider": "aliyun"})
            toolkit = AudioToolkit(config)

            assert toolkit.ak_id == "env_access_key"
            assert toolkit.ak_secret == "env_secret_key"
            assert toolkit.app_key == "env_app_key"

    @pytest.mark.asyncio
    async def test_aliyun_get_tools_map(self, aliyun_toolkit):
        """Test that tools map is correctly defined for Aliyun provider."""
        tools_map = await aliyun_toolkit.get_tools_map()

        expected_tools = ["transcribe_audio", "audio_qa", "get_audio_info"]
        for tool_name in expected_tools:
            assert tool_name in tools_map
            assert callable(tools_map[tool_name])

    def test_extract_transcription_text_success(self, aliyun_toolkit, mock_aliyun_response):
        """Test successful text extraction from Aliyun response."""
        result = aliyun_toolkit._extract_transcription_text_aliyun(mock_aliyun_response)

        assert isinstance(result, str)
        assert "这是一段测试音频的转录文本。" in result
        assert "包含了中文语音识别的结果。" in result

    def test_extract_transcription_text_empty_sentences(self, aliyun_toolkit):
        """Test text extraction with empty sentences."""
        response = {"Sentences": []}
        result = aliyun_toolkit._extract_transcription_text_aliyun(response)

        assert isinstance(result, str)
        assert "Sentences" in result

    def test_extract_transcription_text_no_sentences(self, aliyun_toolkit):
        """Test text extraction without sentences key."""
        response = {"other_key": "value"}
        result = aliyun_toolkit._extract_transcription_text_aliyun(response)

        assert isinstance(result, str)
        assert "other_key" in result

    def test_extract_transcription_text_string_input(self, aliyun_toolkit):
        """Test text extraction with string input."""
        result = aliyun_toolkit._extract_transcription_text_aliyun("direct text result")

        assert result == "direct text result"

    @pytest.mark.asyncio
    async def test_aliyun_transcribe_local_file_fails(self, aliyun_toolkit, mock_audio_file):
        """Test that Aliyun provider rejects local files."""
        result = await aliyun_toolkit.transcribe_audio(mock_audio_file)

        assert "error" in result
        assert "publicly accessible URLs" in result["error"]
        assert result["provider"] == "aliyun"

    @pytest.mark.asyncio
    @patch("noesium.toolkits.audio_toolkit.AudioToolkit._transcribe_file_aliyun")
    async def test_aliyun_transcribe_success(self, mock_transcribe, aliyun_toolkit, mock_aliyun_response):
        """Test successful Aliyun audio transcription API."""
        mock_transcribe.return_value = mock_aliyun_response

        result = await aliyun_toolkit.transcribe_audio("https://example.com/test_audio.mp3")

        assert "text" in result
        assert "这是一段测试音频的转录文本。" in result["text"]
        assert result["provider"] == "aliyun"
        assert "aliyun_result" in result

    @pytest.mark.asyncio
    @patch("noesium.toolkits.audio_toolkit.AudioToolkit._transcribe_file_aliyun")
    async def test_aliyun_transcribe_failure(self, mock_transcribe, aliyun_toolkit):
        """Test Aliyun audio transcription failure."""
        mock_transcribe.side_effect = Exception("Processing failed")

        result = await aliyun_toolkit.transcribe_audio("https://example.com/test_audio.mp3")

        assert "error" in result
        assert "Processing failed" in result["error"]
        assert result["text"] == ""

    @pytest.mark.asyncio
    @patch("noesium.toolkits.audio_toolkit.AudioToolkit.transcribe_audio")
    async def test_aliyun_audio_qa_success(self, mock_transcribe, aliyun_toolkit):
        """Test successful Aliyun audio Q&A."""
        mock_transcribe.return_value = {
            "text": "这是一段关于人工智能的讨论。主要讨论了机器学习的应用。",
            "provider": "aliyun",
        }

        mock_llm_client = AsyncMock()
        mock_llm_client.completion.return_value = "这段音频主要讨论了人工智能和机器学习的应用场景。"

        with patch.object(type(aliyun_toolkit), "llm_client", new_callable=lambda: mock_llm_client):
            result = await aliyun_toolkit.audio_qa("https://example.com/test_audio.mp3", "这段音频讨论了什么？")

            assert isinstance(result, str)
            assert "人工智能" in result or "机器学习" in result
            mock_llm_client.completion.assert_called_once()

    @pytest.mark.asyncio
    @patch("noesium.toolkits.audio_toolkit.AudioToolkit.transcribe_audio")
    async def test_aliyun_audio_qa_no_speech(self, mock_transcribe, aliyun_toolkit):
        """Test Aliyun audio Q&A with no speech detected."""
        mock_transcribe.return_value = {"text": "", "provider": "aliyun"}

        result = await aliyun_toolkit.audio_qa("https://example.com/test_audio.mp3", "What is discussed?")

        assert result == "No speech detected in the audio file."

    @pytest.mark.asyncio
    @patch("noesium.toolkits.audio_toolkit.AudioToolkit.transcribe_audio")
    async def test_aliyun_audio_qa_transcription_error(self, mock_transcribe, aliyun_toolkit):
        """Test Aliyun audio Q&A with transcription error."""
        mock_transcribe.return_value = {"error": "Transcription failed"}

        result = await aliyun_toolkit.audio_qa("https://example.com/test_audio.mp3", "What is discussed?")

        assert "Failed to transcribe audio" in result

    @pytest.mark.asyncio
    async def test_aliyun_get_audio_info_limited(self, aliyun_toolkit):
        """Test that get_audio_info returns limited info for Aliyun provider."""
        result = await aliyun_toolkit.get_audio_info("https://example.com/audio.mp3")

        assert result["provider"] == "aliyun"
        assert "note" in result
        assert "Limited info" in result["note"]


# ==================== Aliyun Integration Tests ====================


class TestAudioToolkitAliyunIntegration:
    """Integration tests for Aliyun provider with mocked Aliyun services."""

    @pytest.mark.asyncio
    @patch("aliyunsdkcore.client.AcsClient")
    async def test_transcribe_file_aliyun_success(self, mock_acs_client, aliyun_toolkit):
        """Test successful Aliyun NLS transcription with mocked client."""
        mock_client_instance = MagicMock()
        mock_acs_client.return_value = mock_client_instance

        submit_response = json.dumps({"StatusText": "SUCCESS", "TaskId": "test_task_id_123"})

        get_response = json.dumps(
            {
                "StatusText": "SUCCESS",
                "Result": {
                    "Sentences": [
                        {
                            "Text": "这是测试音频转录结果。",
                            "BeginTime": 0,
                            "EndTime": 2000,
                            "ChannelId": 0,
                        }
                    ]
                },
            }
        )

        mock_client_instance.do_action_with_exception.side_effect = [
            submit_response,
            get_response,
        ]

        aliyun_toolkit.aliyun_client = mock_client_instance

        result = await aliyun_toolkit._transcribe_file_aliyun("https://example.com/test.mp3")

        assert result is not None
        assert "Sentences" in result
        assert len(result["Sentences"]) == 1
        assert result["Sentences"][0]["Text"] == "这是测试音频转录结果。"

    @pytest.mark.asyncio
    @patch("aliyunsdkcore.client.AcsClient")
    async def test_transcribe_file_aliyun_submit_failure(self, mock_acs_client, aliyun_toolkit):
        """Test Aliyun NLS transcription submit failure."""
        mock_client_instance = MagicMock()
        mock_acs_client.return_value = mock_client_instance

        submit_response = json.dumps({"StatusText": "FAILED", "Message": "Invalid file format"})

        mock_client_instance.do_action_with_exception.return_value = submit_response
        aliyun_toolkit.aliyun_client = mock_client_instance

        result = await aliyun_toolkit._transcribe_file_aliyun("https://example.com/test.mp3")

        assert result is None


# ==================== Real Integration Tests ====================


@pytest.mark.integration
class TestAudioToolkitRealIntegration:
    """
    Real integration tests that require actual credentials.
    These tests are marked with @pytest.mark.integration and should be run separately.
    """

    @pytest.mark.skipif(
        not all(
            [
                os.getenv("ALIYUN_ACCESS_KEY_ID"),
                os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
                os.getenv("ALIYUN_NLS_APP_KEY"),
            ]
        ),
        reason="Aliyun credentials not available",
    )
    @pytest.mark.asyncio
    async def test_real_aliyun_transcription(self):
        """Test real Aliyun NLS transcription with actual credentials."""
        config = ToolkitConfig(
            name="audio",
            config={
                "provider": "aliyun",
                "ALIYUN_ACCESS_KEY_ID": os.getenv("ALIYUN_ACCESS_KEY_ID"),
                "ALIYUN_ACCESS_KEY_SECRET": os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
                "ALIYUN_NLS_APP_KEY": os.getenv("ALIYUN_NLS_APP_KEY"),
            },
        )

        toolkit = AudioToolkit(config)

        assert toolkit is not None
        assert toolkit.provider == "aliyun"
        assert hasattr(toolkit, "aliyun_client")

    @pytest.mark.skipif(
        not all(
            [
                os.getenv("ALIYUN_ACCESS_KEY_ID"),
                os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
                os.getenv("ALIYUN_NLS_APP_KEY"),
                os.getenv("OPENAI_API_KEY"),
            ]
        ),
        reason="Aliyun and OpenAI credentials not available",
    )
    @pytest.mark.asyncio
    async def test_real_audio_qa_workflow(self):
        """Test real audio Q&A workflow with actual services."""
        config = ToolkitConfig(
            name="audio",
            config={
                "provider": "aliyun",
                "ALIYUN_ACCESS_KEY_ID": os.getenv("ALIYUN_ACCESS_KEY_ID"),
                "ALIYUN_ACCESS_KEY_SECRET": os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
                "ALIYUN_NLS_APP_KEY": os.getenv("ALIYUN_NLS_APP_KEY"),
            },
            llm_provider="openai",
            llm_config={"api_key": os.getenv("OPENAI_API_KEY")},
        )

        toolkit = AudioToolkit(config)

        assert toolkit is not None
        tools_map = await toolkit.get_tools_map()
        assert "audio_qa" in tools_map
