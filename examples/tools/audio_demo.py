"""
Demonstration of the AudioToolkit with multiple providers.

This example shows how to use the unified AudioToolkit with different
providers (OpenAI Whisper and Aliyun NLS) for audio transcription and analysis.
"""

import asyncio
import os

from noesium.core.toolify import ToolkitConfig, get_toolkit
from noesium.core.utils.logging import get_logger, setup_logging

# Set up logging (use ERROR to suppress toolkit noise, WARNING for debugging)
setup_logging(level="ERROR")
logger = get_logger(__name__)


async def demo_openai_provider():
    """Demonstrate audio transcription using OpenAI Whisper API."""
    print("\n=== OpenAI Whisper Provider Demo ===")

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set - skipping OpenAI demo")
        return

    # Create toolkit with OpenAI provider (default)
    config = ToolkitConfig(
        name="audio_openai",
        config={
            "provider": "openai",
            "audio_model": "whisper-1",
        },
        llm_provider="openai",
        llm_config={"api_key": os.getenv("OPENAI_API_KEY")},
    )

    toolkit = get_toolkit("audio", config)

    print(f"Toolkit provider: {toolkit.provider}")
    print(f"Audio model: {toolkit.audio_model}")

    # Example 1: Transcribe audio from URL
    print("\n--- Example 1: Transcribe audio from URL ---")
    audio_url = "https://example.com/sample.mp3"  # Replace with actual URL

    print(f"Transcribing: {audio_url}")
    result = await toolkit.call_tool("transcribe_audio", audio_path=audio_url)

    if "error" in result:
        print(f"Transcription error: {result['error']}")
    else:
        print(f"Provider: {result.get('provider')}")
        print(f"Duration: {result.get('duration')} seconds")
        print(f"Language: {result.get('language')}")
        print(f"Transcription: {result.get('text', '')[:200]}...")

        # Show segments if available
        if result.get("segments"):
            print(f"Segments: {len(result['segments'])} segments")
            for seg in result["segments"][:3]:
                print(f"  {seg['start']:.2f}s - {seg['end']:.2f}s: {seg['text']}")

    # Example 2: Get audio info
    print("\n--- Example 2: Get audio info ---")
    info = await toolkit.call_tool("get_audio_info", audio_path=audio_url)
    print(f"Audio info: {info}")


async def demo_aliyun_provider():
    """Demonstrate audio transcription using Aliyun NLS service."""
    print("\n=== Aliyun NLS Provider Demo ===")

    # Check for Aliyun credentials
    if not all(
        [
            os.getenv("ALIYUN_ACCESS_KEY_ID"),
            os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
            os.getenv("ALIYUN_NLS_APP_KEY"),
        ]
    ):
        print("Aliyun credentials not set - skipping Aliyun demo")
        print("Required: ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, ALIYUN_NLS_APP_KEY")
        return

    # Create toolkit with Aliyun provider
    config = ToolkitConfig(
        name="audio_aliyun",
        config={
            "provider": "aliyun",
            "ALIYUN_ACCESS_KEY_ID": os.getenv("ALIYUN_ACCESS_KEY_ID"),
            "ALIYUN_ACCESS_KEY_SECRET": os.getenv("ALIYUN_ACCESS_KEY_SECRET"),
            "ALIYUN_NLS_APP_KEY": os.getenv("ALIYUN_NLS_APP_KEY"),
            "ALIYUN_REGION_ID": os.getenv("ALIYUN_REGION_ID", "cn-shanghai"),
        },
        llm_provider="openai",
        llm_config={"api_key": os.getenv("OPENAI_API_KEY")},
    )

    toolkit = get_toolkit("audio", config)

    print(f"Toolkit provider: {toolkit.provider}")
    print(f"Region: {toolkit.region_id}")

    # Aliyun requires publicly accessible URLs
    audio_url = "https://example.com/chinese-audio.mp3"  # Replace with actual public URL

    print(f"\n--- Transcribing Chinese audio: {audio_url} ---")
    result = await toolkit.call_tool("transcribe_audio", audio_path=audio_url)

    if "error" in result:
        print(f"Transcription error: {result['error']}")
    else:
        print(f"Provider: {result.get('provider')}")
        print(f"Language: {result.get('language')}")
        print(f"Transcription: {result.get('text', '')}")


async def demo_audio_qa():
    """Demonstrate audio Q&A functionality."""
    print("\n=== Audio Q&A Demo ===")

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set - skipping Q&A demo")
        return

    # Create toolkit
    config = ToolkitConfig(
        name="audio_qa",
        config={"provider": "openai"},
        llm_provider="openai",
        llm_config={"api_key": os.getenv("OPENAI_API_KEY")},
    )

    toolkit = get_toolkit("audio", config)

    audio_url = "https://example.com/meeting.mp3"  # Replace with actual URL
    questions = [
        "What are the main topics discussed in this audio?",
        "Who are the speakers and what are their main points?",
        "Summarize the key decisions made in this recording.",
    ]

    for question in questions:
        print(f"\n--- Question: {question} ---")
        answer = await toolkit.call_tool("audio_qa", audio_path=audio_url, question=question)
        print(f"Answer: {answer}")


async def demo_local_file():
    """Demonstrate transcription from a local file (OpenAI provider only)."""
    print("\n=== Local File Transcription Demo ===")

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set - skipping local file demo")
        return

    # Create toolkit with OpenAI provider
    config = ToolkitConfig(
        name="audio_local",
        config={"provider": "openai"},
        llm_provider="openai",
        llm_config={"api_key": os.getenv("OPENAI_API_KEY")},
    )

    toolkit = get_toolkit("audio", config)

    # Example local file path
    local_file = "./sample_audio.mp3"

    # Check if file exists
    if not os.path.exists(local_file):
        print(f"Local file not found: {local_file}")
        print("Create a sample audio file to test local transcription")
        return

    print(f"Transcribing local file: {local_file}")
    result = await toolkit.call_tool("transcribe_audio", audio_path=local_file)

    if "error" in result:
        print(f"Transcription error: {result['error']}")
    else:
        print(f"Transcription: {result.get('text', '')}")


async def demo_provider_comparison():
    """Demonstrate provider comparison and selection."""
    print("\n=== Provider Comparison Demo ===")

    print("\nOpenAI Provider:")
    print("  - Supports both local files and URLs")
    print("  - Automatic downloading from URLs")
    print("  - Detailed transcription with timestamps")
    print("  - Multi-language support")
    print("  - Best for: General-purpose transcription, English content")

    print("\nAliyun Provider:")
    print("  - Requires publicly accessible URLs only")
    print("  - Optimized for Chinese language content")
    print("  - Direct cloud-based transcription")
    print("  - Best for: Chinese audio, when cloud processing is preferred")

    # Show how to switch providers
    print("\n--- Switching Providers ---")

    # Default is OpenAI
    config_default = ToolkitConfig(name="audio_default")
    toolkit_default = get_toolkit("audio", config_default)
    print(f"Default provider: {toolkit_default.provider}")

    # Explicitly select Aliyun (requires credentials)
    try:
        config_aliyun = ToolkitConfig(
            name="audio_aliyun_explicit",
            config={"provider": "aliyun"},
        )
        toolkit_aliyun = get_toolkit("audio", config_aliyun)
        print(f"Aliyun provider: {toolkit_aliyun.provider}")
    except ValueError as e:
        print(f"Aliyun provider not available: {e}")


async def demo_tools_map():
    """Demonstrate available tools in the audio toolkit."""
    print("\n=== Available Tools Demo ===")

    config = ToolkitConfig(name="audio_tools")
    toolkit = get_toolkit("audio", config)

    tools_map = await toolkit.get_tools_map()
    print(f"Available tools: {list(tools_map.keys())}")

    for tool_name, tool_func in tools_map.items():
        print(f"\n{tool_name}:")
        if tool_func.__doc__:
            # Show first few lines of docstring
            lines = tool_func.__doc__.strip().split("\n")[:3]
            for line in lines:
                print(f"  {line.strip()}")


async def main():
    """Run all demonstrations."""
    print("Starting AudioToolkit demonstration")
    print("=" * 60)

    # Show available tools
    await demo_tools_map()

    # Show provider comparison
    await demo_provider_comparison()

    # Run provider-specific demos
    await demo_openai_provider()
    await demo_aliyun_provider()

    # Run Q&A demo
    await demo_audio_qa()

    # Run local file demo
    await demo_local_file()

    print("=" * 60)
    print("Demonstration completed!")


if __name__ == "__main__":
    # Set up environment variables for demo
    # For OpenAI provider:
    # os.environ["OPENAI_API_KEY"] = "your_openai_api_key"

    # For Aliyun provider:
    # os.environ["ALIYUN_ACCESS_KEY_ID"] = "your_access_key_id"
    # os.environ["ALIYUN_ACCESS_KEY_SECRET"] = "your_access_key_secret"
    # os.environ["ALIYUN_NLS_APP_KEY"] = "your_nls_app_key"
    # os.environ["ALIYUN_REGION_ID"] = "cn-shanghai"

    asyncio.run(main())
