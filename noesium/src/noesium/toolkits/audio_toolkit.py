"""
Audio processing toolkit for transcription and analysis.

Provides tools for audio transcription using multiple providers:
- OpenAI Whisper API (default)
- Aliyun NLS service (optimized for Chinese)

Supports audio content analysis using LLMs.
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional
from urllib.parse import urlparse

import aiohttp

try:
    from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.request import CommonRequest

    ALIYUN_AVAILABLE = True
except ImportError:
    ClientException = None
    ServerException = None
    AcsClient = None
    CommonRequest = None
    ALIYUN_AVAILABLE = False

from noesium.core.consts import get_toolkit_tmp_dir
from noesium.core.toolify.base import AsyncBaseToolkit
from noesium.core.toolify.config import ToolkitConfig
from noesium.core.toolify.registry import register_toolkit
from noesium.core.utils.logging import get_logger

# Toolkit registration name
TOOLKIT_AUDIO = "audio"

logger = get_logger(__name__)

AudioProvider = Literal["openai", "aliyun"]


@register_toolkit(TOOLKIT_AUDIO)
class AudioToolkit(AsyncBaseToolkit):
    """
    Unified toolkit for audio processing and analysis supporting multiple providers.

    This toolkit provides capabilities for:
    - Audio transcription using OpenAI's Whisper API or Aliyun's NLS service
    - Audio content analysis and Q&A using LLMs
    - Support for various audio formats
    - URL and local file processing (provider-dependent)
    - Caching of transcription results

    Providers:
    - openai: OpenAI Whisper API (default)
        - Supports both local files and URLs
        - Automatic downloading from URLs
        - Detailed transcription with timestamps
        - Multi-language support
    - aliyun: Aliyun NLS service
        - Requires publicly accessible URLs
        - Optimized for Chinese language content
        - Direct cloud-based transcription

    Features:
    - MD5-based caching to avoid re-transcribing same files
    - LLM-powered audio content analysis
    - Support for multiple audio formats (mp3, wav, m4a, flac, etc.)

    Required configuration:
    - OpenAI provider: OpenAI API key
    - Aliyun provider: Aliyun Access Key ID, Secret, and NLS App Key
    - LLM configuration for analysis
    """

    def __init__(self, config: ToolkitConfig = None):
        """
        Initialize the audio toolkit.

        Args:
            config: Toolkit configuration containing provider settings and API keys

        Configuration options:
            - provider: "openai" or "aliyun" (default: "openai")
            - audio_model: Model for OpenAI transcription (default: "whisper-1")
            - cache_dir: Directory for caching transcription results
            - download_dir: Directory for downloaded audio files
            - ALIYUN_ACCESS_KEY_ID: Aliyun access key ID
            - ALIYUN_ACCESS_KEY_SECRET: Aliyun access key secret
            - ALIYUN_NLS_APP_KEY: Aliyun NLS app key
            - ALIYUN_REGION_ID: Aliyun region (default: "cn-shanghai")
        """
        super().__init__(config)

        # Provider configuration
        self.provider: AudioProvider = self.config.config.get("provider", "openai")

        # Common directories
        self.cache_dir = Path(
            self.config.config.get(
                "cache_dir", get_toolkit_tmp_dir(TOOLKIT_AUDIO, "cache")
            )
        )
        self.download_dir = Path(
            self.config.config.get(
                "download_dir", get_toolkit_tmp_dir(TOOLKIT_AUDIO, "downloads")
            )
        )

        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # Cache for MD5 to file path mapping
        self.md5_to_path: Dict[str, str] = {}

        # Provider-specific setup
        if self.provider == "aliyun":
            self._setup_aliyun()
        elif self.provider == "openai":
            self._setup_openai()
        else:
            raise ValueError(
                f"Unsupported audio provider: {self.provider}. Supported: 'openai', 'aliyun'"
            )

    def _setup_openai(self) -> None:
        """Setup OpenAI provider configuration."""
        self.audio_model = self.config.config.get("audio_model", "whisper-1")

    def _setup_aliyun(self) -> None:
        """Setup Aliyun provider configuration."""
        if not ALIYUN_AVAILABLE:
            raise ImportError(
                "Aliyun packages are not installed. Install them with: pip install 'noesium[aliyun]'"
            )

        # Aliyun credentials
        self.ak_id = self.config.config.get("ALIYUN_ACCESS_KEY_ID") or os.getenv(
            "ALIYUN_ACCESS_KEY_ID"
        )
        self.ak_secret = self.config.config.get(
            "ALIYUN_ACCESS_KEY_SECRET"
        ) or os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        self.app_key = self.config.config.get("ALIYUN_NLS_APP_KEY") or os.getenv(
            "ALIYUN_NLS_APP_KEY"
        )
        self.region_id = self.config.config.get("ALIYUN_REGION_ID", "cn-shanghai")

        if not all([self.ak_id, self.ak_secret, self.app_key]):
            raise ValueError(
                "Aliyun credentials not found. Please set ALIYUN_ACCESS_KEY_ID, "
                "ALIYUN_ACCESS_KEY_SECRET, and ALIYUN_NLS_APP_KEY in config or environment"
            )

        # Aliyun NLS service constants
        self.ALIYUN_PRODUCT = "nls-filetrans"
        self.ALIYUN_DOMAIN = f"filetrans.{self.region_id}.aliyuncs.com"
        self.ALIYUN_API_VERSION = "2018-08-17"
        self.ALIYUN_POST_REQUEST_ACTION = "SubmitTask"
        self.ALIYUN_GET_REQUEST_ACTION = "GetTaskResult"

        # Request parameters
        self.ALIYUN_KEY_APPKEY = "appkey"
        self.ALIYUN_KEY_FILE_LINK = "file_link"
        self.ALIYUN_KEY_VERSION = "version"
        self.ALIYUN_KEY_ENABLE_WORDS = "enable_words"
        self.ALIYUN_KEY_AUTO_SPLIT = "auto_split"

        # Response parameters
        self.ALIYUN_KEY_TASK = "Task"
        self.ALIYUN_KEY_TASK_ID = "TaskId"
        self.ALIYUN_KEY_STATUS_TEXT = "StatusText"
        self.ALIYUN_KEY_RESULT = "Result"

        # Status values
        self.ALIYUN_STATUS_SUCCESS = "SUCCESS"
        self.ALIYUN_STATUS_RUNNING = "RUNNING"
        self.ALIYUN_STATUS_QUEUEING = "QUEUEING"

        # Create AcsClient instance
        self.aliyun_client = AcsClient(self.ak_id, self.ak_secret, self.region_id)

    # ==================== Common Utility Methods ====================

    def _get_file_md5(self, file_path: str) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _is_url(self, path: str) -> bool:
        """Check if the path is a URL."""
        try:
            result = urlparse(path)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _get_file_extension(self, path: str) -> str:
        """Get file extension from path or URL."""
        parsed = urlparse(path)
        return Path(parsed.path).suffix or ".mp3"  # Default to .mp3

    async def _download_audio(self, url: str, output_path: Path) -> Path:
        """Download audio file from URL."""
        self.logger.info(f"Downloading audio from: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()

                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

            self.logger.info(f"Audio downloaded to: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to download audio: {e}")
            raise

    async def _handle_audio_path_openai(self, audio_path: str) -> str:
        """
        Handle audio path for OpenAI - download if URL, calculate MD5, and cache.

        Args:
            audio_path: Path or URL to audio file

        Returns:
            MD5 hash of the audio file
        """
        if self._is_url(audio_path):
            ext = self._get_file_extension(audio_path)
            url_hash = hashlib.md5(audio_path.encode()).hexdigest()[:8]
            local_path = self.download_dir / f"{url_hash}{ext}"

            if not local_path.exists():
                await self._download_audio(audio_path, local_path)

            file_path = str(local_path)
        else:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            file_path = audio_path

        md5_hash = self._get_file_md5(file_path)
        self.md5_to_path[md5_hash] = file_path

        return md5_hash

    # ==================== OpenAI Provider Methods ====================

    async def _transcribe_openai(self, md5_hash: str) -> Dict:
        """
        Transcribe audio file using OpenAI's Whisper API.

        Args:
            md5_hash: MD5 hash of the audio file

        Returns:
            Transcription result with text and metadata
        """
        # Check cache first
        cache_file = self.cache_dir / f"{md5_hash}.json"
        if cache_file.exists():
            with open(cache_file, "r") as f:
                return json.load(f)

        # Get file path
        if md5_hash not in self.md5_to_path:
            raise ValueError(f"Audio file with MD5 {md5_hash} not found in cache")

        file_path = self.md5_to_path[md5_hash]

        try:
            import openai

            # Get OpenAI client from LLM client
            client = (
                self.llm_client._client if hasattr(self.llm_client, "_client") else None
            )
            if not client:
                api_key = self.config.config.get("OPENAI_API_KEY") or os.getenv(
                    "OPENAI_API_KEY"
                )
                if not api_key:
                    raise ValueError(
                        "OpenAI API key not found in config or environment"
                    )
                client = openai.AsyncOpenAI(api_key=api_key)

            self.logger.info(f"Transcribing audio file with OpenAI: {file_path}")

            with open(file_path, "rb") as audio_file:
                transcript = await client.audio.transcriptions.create(
                    model=self.audio_model,
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=(
                        ["segment"] if self.audio_model != "whisper-1" else None
                    ),
                )

            # Convert to dict and cache
            result = (
                transcript.model_dump()
                if hasattr(transcript, "model_dump")
                else dict(transcript)
            )
            result["provider"] = "openai"

            # Cache the result
            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)

            self.logger.info(
                f"Transcription completed, duration: {result.get('duration', 'unknown')}s"
            )
            return result

        except Exception as e:
            self.logger.error(f"OpenAI transcription failed: {e}")
            raise

    # ==================== Aliyun Provider Methods ====================

    async def _transcribe_file_aliyun(self, file_link: str) -> Optional[Dict[str, Any]]:
        """
        Perform file transcription using Aliyun NLS service.

        Args:
            file_link: URL of the audio file to transcribe

        Returns:
            Transcription result dictionary or None if failed
        """
        # Submit transcription request
        post_request = CommonRequest()
        post_request.set_domain(self.ALIYUN_DOMAIN)
        post_request.set_version(self.ALIYUN_API_VERSION)
        post_request.set_product(self.ALIYUN_PRODUCT)
        post_request.set_action_name(self.ALIYUN_POST_REQUEST_ACTION)
        post_request.set_method("POST")

        task = {
            self.ALIYUN_KEY_APPKEY: self.app_key,
            self.ALIYUN_KEY_FILE_LINK: file_link,
            self.ALIYUN_KEY_VERSION: "4.0",
            self.ALIYUN_KEY_ENABLE_WORDS: False,
        }

        task_json = json.dumps(task)
        self.logger.info(f"Submitting Aliyun task: {task_json}")
        post_request.add_body_params(self.ALIYUN_KEY_TASK, task_json)

        task_id = ""
        try:
            loop = asyncio.get_event_loop()
            post_response = await loop.run_in_executor(
                None, self.aliyun_client.do_action_with_exception, post_request
            )
            post_response_json = json.loads(post_response)
            self.logger.info(f"Aliyun submit response: {post_response_json}")

            status_text = post_response_json[self.ALIYUN_KEY_STATUS_TEXT]
            if status_text == self.ALIYUN_STATUS_SUCCESS:
                self.logger.info("Aliyun transcription request submitted successfully!")
                task_id = post_response_json[self.ALIYUN_KEY_TASK_ID]
            else:
                self.logger.error(f"Aliyun transcription request failed: {status_text}")
                return None
        except ServerException as e:
            self.logger.error(f"Aliyun server error: {e}")
            return None
        except ClientException as e:
            self.logger.error(f"Aliyun client error: {e}")
            return None

        if not task_id:
            self.logger.error("No Aliyun task ID received")
            return None

        # Create request to get task result
        get_request = CommonRequest()
        get_request.set_domain(self.ALIYUN_DOMAIN)
        get_request.set_version(self.ALIYUN_API_VERSION)
        get_request.set_product(self.ALIYUN_PRODUCT)
        get_request.set_action_name(self.ALIYUN_GET_REQUEST_ACTION)
        get_request.set_method("GET")
        get_request.add_query_param(self.ALIYUN_KEY_TASK_ID, task_id)

        # Poll for results
        self.logger.info(f"Polling for Aliyun results with task ID: {task_id}")
        status_text = ""
        max_attempts = 60
        attempt = 0

        while attempt < max_attempts:
            try:
                get_response = await loop.run_in_executor(
                    None, self.aliyun_client.do_action_with_exception, get_request
                )
                get_response_json = json.loads(get_response)
                self.logger.info(
                    f"Aliyun poll response (attempt {attempt + 1}): {get_response_json}"
                )

                status_text = get_response_json[self.ALIYUN_KEY_STATUS_TEXT]
                if status_text in (
                    self.ALIYUN_STATUS_RUNNING,
                    self.ALIYUN_STATUS_QUEUEING,
                ):
                    await asyncio.sleep(10)
                    attempt += 1
                else:
                    break
            except ServerException as e:
                self.logger.error(f"Aliyun server error during polling: {e}")
                return None
            except ClientException as e:
                self.logger.error(f"Aliyun client error during polling: {e}")
                return None

        if status_text == self.ALIYUN_STATUS_SUCCESS:
            self.logger.info("Aliyun transcription completed successfully!")
            return get_response_json.get(self.ALIYUN_KEY_RESULT)
        else:
            self.logger.error(f"Aliyun transcription failed with status: {status_text}")
            return None

    def _extract_transcription_text_aliyun(
        self, result: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extract transcription text from the Aliyun NLS result.

        Args:
            result: The result from Aliyun NLS transcription

        Returns:
            Extracted transcription text or None if extraction fails
        """
        try:
            if isinstance(result, dict) and "Sentences" in result:
                sentences = result["Sentences"]
                if isinstance(sentences, list):
                    unique_texts = set()
                    for sentence in sentences:
                        if isinstance(sentence, dict) and "Text" in sentence:
                            text = sentence["Text"].strip()
                            if text:
                                unique_texts.add(text)

                    if unique_texts:
                        transcription_parts = sorted(list(unique_texts))
                        return " ".join(transcription_parts)

            if isinstance(result, dict):
                for key in ["text", "transcription", "content", "result"]:
                    if key in result:
                        return str(result[key])

                return json.dumps(result, ensure_ascii=False)

            if isinstance(result, str):
                return result

        except Exception as e:
            self.logger.error(f"Error extracting Aliyun transcription text: {str(e)}")
            return None

        return None

    async def _transcribe_aliyun(self, audio_path: str) -> Dict:
        """
        Transcribe audio using Aliyun NLS service.

        Args:
            audio_path: URL of the audio file (must be publicly accessible)

        Returns:
            Transcription result with text and metadata
        """
        try:
            aliyun_result = await self._transcribe_file_aliyun(audio_path)
            if aliyun_result is None:
                return {
                    "error": "Aliyun NLS transcription failed",
                    "text": "",
                    "provider": "aliyun",
                }

            transcription_text = self._extract_transcription_text_aliyun(aliyun_result)
            if transcription_text is None:
                return {
                    "error": "Failed to extract text from Aliyun NLS result",
                    "text": "",
                    "provider": "aliyun",
                }

            return {
                "text": transcription_text,
                "aliyun_result": aliyun_result,
                "provider": "aliyun",
                "language": "zh",
            }

        except Exception as e:
            error_msg = f"Aliyun audio transcription failed: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "text": "", "provider": "aliyun"}

    # ==================== Public API Methods ====================

    async def transcribe_audio(self, audio_path: str) -> Dict:
        """
        Transcribe an audio file to text.

        This tool converts speech in audio files to text using the configured provider.
        It supports various audio formats and can handle both local files and URLs
        (provider-dependent).

        Provider-specific behavior:
        - OpenAI (default): Supports both local files and URLs. Automatically downloads
          URLs for processing. Provides detailed transcription with timestamps.
        - Aliyun: Requires publicly accessible URLs. Optimized for Chinese content.
          Does not support local files directly.

        Features:
        - Supports multiple audio formats (mp3, wav, m4a, flac, etc.)
        - Automatic downloading from URLs (OpenAI provider)
        - Caching to avoid re-transcribing the same files
        - Detailed output with timestamps (OpenAI provider)
        - Duration and language detection (OpenAI provider)

        Args:
            audio_path: Path to local audio file or URL to audio file.
                       For Aliyun provider, must be a publicly accessible URL.

        Returns:
            Dictionary containing:
            - text: The transcribed text
            - duration: Audio duration in seconds (OpenAI only)
            - language: Detected language (if available)
            - segments: Timestamped segments (OpenAI only, if available)
            - provider: The transcription provider used
            - error: Error message if transcription failed

        Example:
            result = await transcribe_audio("https://example.com/audio.mp3")
            print(result["text"])  # Full transcription
            for segment in result.get("segments", []):
                print(f"{segment['start']:.2f}s: {segment['text']}")
        """
        try:
            if self.provider == "aliyun":
                if not self._is_url(audio_path):
                    return {
                        "error": "Aliyun provider requires publicly accessible URLs. Local files are not supported.",
                        "text": "",
                        "provider": "aliyun",
                    }
                return await self._transcribe_aliyun(audio_path)
            else:  # openai
                md5_hash = await self._handle_audio_path_openai(audio_path)
                result = await self._transcribe_openai(md5_hash)
                return result

        except Exception as e:
            error_msg = f"Audio transcription failed: {str(e)}"
            self.logger.error(error_msg)
            return {"error": error_msg, "text": "", "provider": self.provider}

    async def audio_qa(self, audio_path: str, question: str) -> str:
        """
        Ask questions about audio content.

        This tool transcribes audio content and then uses an LLM to answer
        questions about the audio based on the transcription. It's useful for
        analyzing conversations, lectures, interviews, or any spoken content.

        Use cases:
        - Summarizing audio content
        - Extracting key information from recordings
        - Answering specific questions about audio content
        - Analyzing sentiment or themes in audio

        Args:
            audio_path: Path to local audio file or URL to audio file.
                       For Aliyun provider, must be a publicly accessible URL.
            question: Question to ask about the audio content

        Returns:
            Answer to the question based on the audio content

        Examples:
            - "What are the main topics discussed in this meeting?"
            - "Who are the speakers and what are their main points?"
            - "Summarize the key decisions made in this recording"
            - "What is the overall sentiment of this conversation?"
        """
        self.logger.info(f"Processing audio Q&A for: {audio_path}")
        self.logger.info(f"Question: {question}")

        try:
            # Transcribe the audio
            transcription_result = await self.transcribe_audio(audio_path)

            if "error" in transcription_result:
                return f"Failed to transcribe audio: {transcription_result['error']}"

            transcription_text = transcription_result.get("text", "")
            duration = transcription_result.get("duration", "unknown")
            provider_name = transcription_result.get("provider", self.provider)

            if not transcription_text.strip():
                return "No speech detected in the audio file."

            # Prepare prompt for LLM analysis
            if provider_name == "aliyun":
                prompt = f"""基于以下音频转录内容，请回答问题。

音频文件: {audio_path}
转录服务: 阿里云语音识别 (Aliyun NLS)
转录内容:
{transcription_text}

问题: {question}

请基于上述音频内容提供清晰、详细的答案。如果转录内容不足以回答问题，请明确说明。"""
                system_message = "你是一个专门分析音频内容的助手。请基于提供的转录内容提供清晰、准确的答案。"
            else:
                prompt = f"""Based on the following audio transcription, please answer the question.

Audio File: {audio_path}
Duration: {duration} seconds
Transcription:
{transcription_text}

Question: {question}

Please provide a clear, detailed answer based on the audio content above. If the transcription doesn't contain enough information to answer the question, please state that clearly."""
                system_message = "You are a helpful assistant specializing in audio content analysis. Provide clear, accurate answers based on the provided transcription."

            # Use LLM to analyze and answer
            response = await self.llm_client.completion(
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )

            return response.strip()

        except Exception as e:
            error_msg = f"Audio Q&A failed: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

    async def get_audio_info(self, audio_path: str) -> Dict:
        """
        Get information about an audio file including transcription metadata.

        Note: This method is only supported for the OpenAI provider.
        For Aliyun provider, it returns limited information.

        Args:
            audio_path: Path to local audio file or URL to audio file

        Returns:
            Dictionary with audio information and transcription metadata
        """
        try:
            if self.provider == "aliyun":
                return {
                    "file_path": audio_path,
                    "provider": "aliyun",
                    "note": "Limited info available for Aliyun provider. Use transcribe_audio for full results.",
                }

            md5_hash = await self._handle_audio_path_openai(audio_path)
            file_path = self.md5_to_path[md5_hash]

            # Get basic file info
            file_stat = os.stat(file_path)
            file_size = file_stat.st_size

            # Get transcription info
            transcription_result = await self._transcribe_openai(md5_hash)

            return {
                "file_path": audio_path,
                "local_path": file_path,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "md5_hash": md5_hash,
                "duration_seconds": transcription_result.get("duration"),
                "detected_language": transcription_result.get("language"),
                "transcription_length": len(transcription_result.get("text", "")),
                "has_segments": "segments" in transcription_result,
                "segment_count": len(transcription_result.get("segments", [])),
                "provider": "openai",
            }

        except Exception as e:
            return {
                "error": f"Failed to get audio info: {str(e)}",
                "provider": self.provider,
            }

    async def get_tools_map(self) -> Dict[str, Callable]:
        """
        Get the mapping of tool names to their implementation functions.

        Returns:
            Dictionary mapping tool names to callable functions
        """
        return {
            "transcribe_audio": self.transcribe_audio,
            "audio_qa": self.audio_qa,
            "get_audio_info": self.get_audio_info,
        }
