"""
LLM Adapter for Noesium to browser-use

This module provides LLM compatibility types and adapters to bridge between
noesium's LLM infrastructure and the community browser-use repository.
"""

import asyncio
import logging
from typing import Any, Generic, Literal, TypeVar, Union

import dotenv
from pydantic import BaseModel

from noesium.core.llm import BaseLLMClient

logger = logging.getLogger(__name__)

dotenv.load_dotenv()

################################################################################
# Browser-use compatibility types
################################################################################

# Define the TypeVar for generic typing
T = TypeVar("T")


class ChatInvokeUsage(BaseModel):
    """
    Usage information for a chat model invocation.
    """

    prompt_tokens: int
    """The number of tokens in the prompt (this includes the cached tokens as well. When calculating the cost, subtract the cached tokens from the prompt tokens)"""

    prompt_cached_tokens: int | None
    """The number of cached tokens."""

    prompt_cache_creation_tokens: int | None
    """Anthropic only: The number of tokens used to create the cache."""

    prompt_image_tokens: int | None
    """Google only: The number of tokens in the image (prompt tokens is the text tokens + image tokens in that case)"""

    completion_tokens: int
    """The number of tokens in the completion."""

    total_tokens: int
    """The total number of tokens in the response."""


class ChatInvokeCompletion(BaseModel, Generic[T]):
    completion: T
    thinking: str | None = None
    redacted_thinking: str | None = None
    usage: ChatInvokeUsage | None = None
    stop_reason: str | None = None


class ModelError(Exception):
    pass


class ModelProviderError(ModelError):
    def __init__(self, message: str, status_code: int = 502, model: str | None = None):
        super().__init__(message, status_code)
        self.model = model


class ModelRateLimitError(ModelProviderError):
    def __init__(self, message: str, status_code: int = 429, model: str | None = None):
        super().__init__(message, status_code, model)


# Define message types for compatibility
class ContentPartTextParam(BaseModel):
    text: str
    type: Literal["text"] = "text"


class ContentPartRefusalParam(BaseModel):
    refusal: str
    type: Literal["refusal"] = "refusal"


class ContentPartImageParam(BaseModel):
    image_url: Any
    type: Literal["image_url"] = "image_url"


class ImageURL(BaseModel):
    url: str
    detail: Literal["auto", "low", "high"] = "auto"
    media_type: Literal["image/jpeg", "image/png", "image/gif", "image/webp"] = "image/png"


class _MessageBase(BaseModel):
    role: Literal["user", "system", "assistant"]
    cache: bool = False


class UserMessage(_MessageBase):
    role: Literal["user"] = "user"
    content: str | list[ContentPartTextParam | ContentPartImageParam]
    name: str | None = None

    @property
    def text(self) -> str:
        """Get text content from message (excluding image URLs for size calculation)."""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, list):
            text_parts = []
            for part in self.content:
                if isinstance(part, ContentPartTextParam):
                    text_parts.append(part.text)
                elif isinstance(part, ContentPartImageParam):
                    # Skip images - they are handled separately
                    continue
            return "\n".join(text_parts)
        return str(self.content)


class SystemMessage(_MessageBase):
    role: Literal["system"] = "system"
    content: str | list[ContentPartTextParam]
    name: str | None = None


class AssistantMessage(_MessageBase):
    role: Literal["assistant"] = "assistant"
    content: str | list[ContentPartTextParam | ContentPartRefusalParam] | None
    name: str | None = None
    refusal: str | None = None
    tool_calls: list = []


BaseMessage = Union[UserMessage, SystemMessage, AssistantMessage]
ContentText = ContentPartTextParam
ContentRefusal = ContentPartRefusalParam
ContentImage = ContentPartImageParam


# Define the BaseChatModel class for compatibility
# Using a regular class instead of Protocol for Pydantic compatibility
class BaseChatModel:
    """Base chat model that adapts noesium LLM clients for browser-use compatibility."""

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize Base Chat Model

        Args:
            llm_client: noesium LLM client to adapt
        """
        self.llm_client = llm_client
        self._verified_api_keys = True  # Assume the noesium client is properly configured

    @property
    def provider(self) -> str:
        """Return provider name if available"""
        return getattr(self.llm_client, "provider", "unknown")

    @property
    def name(self) -> str:
        """Return the model name."""
        return self.model

    @property
    def model(self) -> str:
        """Return model name"""
        return self.model_name

    @property
    def model_name(self) -> str:
        """Return the model name for legacy support."""
        return getattr(self.llm_client, "chat_model", getattr(self.llm_client, "model", "unknown"))

    async def ainvoke(
        self, messages: list[BaseMessage], output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """Invoke the LLM with messages."""
        try:
            # Convert browser-use messages to noesium format
            noesium_messages = []
            total_chars = 0
            image_count = 0

            for msg in messages:
                if hasattr(msg, "role"):
                    # Extract text content properly from browser-use message objects
                    content_text = ""
                    has_images = False

                    if hasattr(msg, "text"):
                        # Use the convenient .text property that handles both string and list formats
                        content_text = msg.text
                    elif hasattr(msg, "content"):
                        # Fallback: handle content directly
                        if isinstance(msg.content, str):
                            content_text = msg.content
                        elif isinstance(msg.content, list):
                            # Extract text from content parts and count images
                            text_parts = []
                            for part in msg.content:
                                if hasattr(part, "type"):
                                    if part.type == "text":
                                        text_parts.append(part.text)
                                    elif part.type == "image_url":
                                        has_images = True
                                        image_count += 1
                                        # Estimate image size (base64 encoded ~500k chars typical)
                                        total_chars += 500000
                            content_text = "\n".join(text_parts)
                        else:
                            content_text = str(msg.content)
                    else:
                        content_text = str(msg)

                    total_chars += len(content_text)
                    noesium_messages.append({"role": msg.role, "content": content_text, "has_images": has_images})
                elif isinstance(msg, dict):
                    # Already in the right format
                    if "content" in msg:
                        total_chars += len(str(msg["content"]))
                    noesium_messages.append(msg)
                else:
                    # Handle other message formats
                    content = str(msg)
                    total_chars += len(content)
                    noesium_messages.append({"role": "user", "content": content})

            # Log message size for debugging
            logger.info(
                f"LLM request: {len(noesium_messages)} messages, {image_count} images, "
                f"~{total_chars} characters (~{total_chars // 4} tokens)"
            )

            # Apply hard limit to prevent exceeding 200k tokens (~800k chars)
            # Use 700k to leave room for system prompt and schema
            MAX_REQUEST_SIZE = 700000  # ~175k tokens
            if total_chars > MAX_REQUEST_SIZE:
                logger.warning(
                    f"Large message size {total_chars} chars exceeds limit {MAX_REQUEST_SIZE}, "
                    f"removing images and truncating text"
                )
                # Remove all images first to save space
                for msg in noesium_messages:
                    msg.pop("has_images", None)

                # Recalculate without images
                total_chars = sum(len(str(msg.get("content", ""))) for msg in noesium_messages)

                # If still too large, truncate text
                if total_chars > MAX_REQUEST_SIZE:
                    truncated_messages = []
                    current_size = 0
                    for msg in noesium_messages:
                        msg_str = str(msg.get("content", ""))
                        if current_size + len(msg_str) > MAX_REQUEST_SIZE:
                            truncated = (MAX_REQUEST_SIZE - current_size - 20) // 2
                            msg_str = msg_str[:truncated]
                            msg_str += "... [Truncated...]"
                        truncated_messages.append(msg)
                        current_size += len(msg_str)
                        if current_size >= MAX_REQUEST_SIZE:
                            break
                    noesium_messages = truncated_messages
                    logger.warning(
                        f"Truncated from {len(noesium_messages)} to {len(truncated_messages)} messages to fit"
                    )

            # Choose completion method based on output_format

            # Choose completion method based on output_format
            if output_format is not None:
                # Use structured completion for structured output
                try:
                    if asyncio.iscoroutinefunction(self.llm_client.structured_completion):
                        structured_response = await self.llm_client.structured_completion(
                            noesium_messages, output_format
                        )
                    else:
                        structured_response = self.llm_client.structured_completion(noesium_messages, output_format)
                    return ChatInvokeCompletion(completion=structured_response)
                except Exception as e:
                    logger.error(f"Error in structured completion: {e}")
                    raise
            else:
                # Use regular completion for string output
                if asyncio.iscoroutinefunction(self.llm_client.completion):
                    response = await self.llm_client.completion(noesium_messages)
                else:
                    response = self.llm_client.completion(noesium_messages)

                return ChatInvokeCompletion(completion=str(response))

        except Exception as e:
            logger.error(f"Error in LLM adapter: {e}")
            raise


class NoesiumLLMAdapter(BaseChatModel):
    """
    Adapter that wraps noesium's LLM client for use with browser-use agents.

    This adapter bridges the gap between noesium's BaseLLMClient interface
    and browser-use's expected LLM interface.
    """

    def __init__(self, llm_client: BaseLLMClient):
        """
        Initialize the adapter with a noesium LLM client.

        Args:
            llm_client: A noesium BaseLLMClient instance
        """
        super().__init__(llm_client)

    async def ainvoke(
        self, messages: list, output_format: type[T] | None = None
    ) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
        """
        Invoke the LLM with messages.

        Args:
            messages: List of messages to send to the LLM
            output_format: Optional Pydantic model for structured output

        Returns:
            ChatInvokeCompletion with the LLM response
        """
        return await super().ainvoke(messages, output_format)

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"NoesiumLLMAdapter(model={self.model_name}, provider={self.provider})"


def create_llm_adapter(llm_client: BaseLLMClient) -> NoesiumLLMAdapter:
    """
    Create a browser-use compatible LLM adapter from a noesium LLM client.

    Args:
        llm_client: A noesium BaseLLMClient instance

    Returns:
        NoesiumLLMAdapter instance
    """
    return NoesiumLLMAdapter(llm_client)


__all__ = [
    # Types
    "ChatInvokeUsage",
    "ChatInvokeCompletion",
    "BaseChatModel",
    "ModelProviderError",
    "ModelRateLimitError",
    "ImageURL",
    # Message types
    "BaseMessage",
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "ContentText",
    "ContentRefusal",
    "ContentImage",
    # Adapters
    "NoesiumLLMAdapter",
    "create_llm_adapter",
]
