from __future__ import annotations

import base64
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, Union

import numpy as np
import pipmaster as pm
import tiktoken
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..utils import VERBOSE_DEBUG, verbose_debug

# install specific modules
if not pm.is_installed("openai"):
    pm.install("openai")

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)
from rag.types import GPTKeywordExtractionFormat
from rag.utils import (
    logger,
    safe_unicode_decode,
    wrap_embedding_func_with_attrs,
)

# Try to import Langfuse for LLM observability (optional)
LANGFUSE_ENABLED = False
try:
    langfuse_public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if langfuse_public_key and langfuse_secret_key:
        from langfuse.openai import AsyncOpenAI  # type: ignore[import-untyped]

        LANGFUSE_ENABLED = True
        logger.info("Langfuse observability enabled for OpenAI client")
    else:
        from openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI

load_dotenv(dotenv_path=".env", override=False)


class InvalidResponseError(Exception):
    """Custom exception class for triggering retry mechanism"""

    pass


# Module-level cache for tiktoken encodings
_TIKTOKEN_ENCODING_CACHE: dict[str, Any] = {}


def _get_tiktoken_encoding_for_model(model: str) -> Any:
    if model not in _TIKTOKEN_ENCODING_CACHE:
        try:
            _TIKTOKEN_ENCODING_CACHE[model] = tiktoken.encoding_for_model(model)
        except KeyError:
            _TIKTOKEN_ENCODING_CACHE[model] = tiktoken.get_encoding("cl100k_base")
    return _TIKTOKEN_ENCODING_CACHE[model]


def create_openai_async_client(
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int | None = None,
    client_configs: dict[str, Any] | None = None,
) -> AsyncOpenAI:
    if not api_key:
        api_key = os.environ["OPENAI_API_KEY"]

    if client_configs is None:
        client_configs = {}

    default_headers = {
        "User-Agent": "Mozilla/5.0 RAG/1.4.10",
        "Content-Type": "application/json",
    }

    if "default_headers" in client_configs:
        default_headers.update(client_configs.pop("default_headers"))

    merged_configs = {
        **client_configs,
        "default_headers": default_headers,
        "api_key": api_key,
    }

    if base_url is not None:
        merged_configs["base_url"] = base_url
    else:
        merged_configs["base_url"] = os.environ.get(
            "OPENAI_API_BASE", "https://api.openai.com/v1"
        )

    if timeout is not None:
        merged_configs["timeout"] = timeout

    return AsyncOpenAI(**merged_configs)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(RateLimitError)
        | retry_if_exception_type(APIConnectionError)
        | retry_if_exception_type(APITimeoutError)
        | retry_if_exception_type(InvalidResponseError)
    ),
)
async def openai_complete_if_cache(
    model: str,
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, Any]] | None = None,
    enable_cot: bool = False,
    base_url: str | None = None,
    api_key: str | None = None,
    token_tracker: Any | None = None,
    stream: bool | None = None,
    timeout: int | None = None,
    keyword_extraction: bool = False,
    **kwargs: Any,
) -> Union[str, AsyncIterator[str]]:
    """Call OpenAI API with retry and error handling."""
    if history_messages is None:
        history_messages = []

    if not VERBOSE_DEBUG and logger.level == logging.DEBUG:
        logging.getLogger("openai").setLevel(logging.INFO)

    # Remove special kwargs that shouldn't be passed to OpenAI
    kwargs.pop("hashing_kv", None)
    client_configs = kwargs.pop("openai_client_configs", {})

    if keyword_extraction:
        kwargs["response_format"] = GPTKeywordExtractionFormat

    openai_async_client = create_openai_async_client(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        client_configs=client_configs,
    )

    # Prepare messages
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})

    logger.debug(f"===== LLM Call: {model} | Base URL: {base_url} =====")
    logger.debug(f"History messages: {len(history_messages)}")
    verbose_debug(f"System prompt: {system_prompt}")
    verbose_debug(f"Query: {prompt}")

    messages = kwargs.pop("messages", messages)

    if stream is not None:
        kwargs["stream"] = stream
    if timeout is not None:
        kwargs["timeout"] = timeout

    try:
        if "response_format" in kwargs:
            response = await openai_async_client.chat.completions.parse(
                model=model, messages=messages, **kwargs
            )
        else:
            response = await openai_async_client.chat.completions.create(
                model=model, messages=messages, **kwargs
            )
    except (APITimeoutError, APIConnectionError, RateLimitError):
        await openai_async_client.close()
        raise
    except Exception as e:
        logger.error(f"OpenAI API Call Failed, Model: {model}, Got: {e}")
        await openai_async_client.close()
        raise

    # --- Streaming response ---
    if hasattr(response, "__aiter__"):

        async def inner():
            iteration_started = False
            final_chunk_usage = None
            cot_active = False
            cot_started = False
            initial_content_seen = False

            try:
                iteration_started = True
                async for chunk in response:
                    if hasattr(chunk, "usage") and chunk.usage:
                        final_chunk_usage = chunk.usage

                    if not hasattr(chunk, "choices") or not chunk.choices:
                        continue
                    if not hasattr(chunk.choices[0], "delta"):
                        continue

                    delta = chunk.choices[0].delta
                    content = getattr(delta, "content", None)
                    reasoning_content = getattr(delta, "reasoning_content", "")

                    if enable_cot:
                        if content:
                            if not initial_content_seen:
                                initial_content_seen = True
                                if reasoning_content:
                                    cot_active = False
                                    cot_started = False
                            if cot_active:
                                yield "</think>"
                                cot_active = False
                            if r"\u" in content:
                                content = safe_unicode_decode(content.encode("utf-8"))
                            yield content
                        elif reasoning_content:
                            if not initial_content_seen and not cot_started:
                                if not cot_active:
                                    yield "<think>"
                                    cot_active = True
                                    cot_started = True
                            if cot_active:
                                if r"\u" in reasoning_content:
                                    reasoning_content = safe_unicode_decode(
                                        reasoning_content.encode("utf-8")
                                    )
                                yield reasoning_content
                    else:
                        if content:
                            if r"\u" in content:
                                content = safe_unicode_decode(content.encode("utf-8"))
                            yield content

                if enable_cot and cot_active:
                    yield "</think>"

                if token_tracker and final_chunk_usage:
                    token_tracker.add_usage(
                        {
                            "prompt_tokens": getattr(
                                final_chunk_usage, "prompt_tokens", 0
                            ),
                            "completion_tokens": getattr(
                                final_chunk_usage, "completion_tokens", 0
                            ),
                            "total_tokens": getattr(
                                final_chunk_usage, "total_tokens", 0
                            ),
                        }
                    )
            except Exception as e:
                if enable_cot and cot_active:
                    try:
                        yield "</think>"
                    except Exception:
                        pass
                logger.error(f"Error in stream response: {e}")
                await openai_async_client.close()
                raise
            finally:
                if iteration_started and hasattr(response, "aclose"):
                    aclose_method = getattr(response, "aclose", None)
                    if callable(aclose_method):
                        try:
                            await response.aclose()
                        except Exception:
                            pass
                try:
                    await openai_async_client.close()
                except Exception:
                    pass

        return inner()

    # --- Non-streaming response ---
    else:
        try:
            if (
                not response
                or not response.choices
                or not hasattr(response.choices[0], "message")
            ):
                await openai_async_client.close()
                raise InvalidResponseError("Invalid response from OpenAI API")

            message = response.choices[0].message

            if hasattr(message, "parsed") and message.parsed is not None:
                final_content = message.parsed.model_dump_json()
            else:
                content = getattr(message, "content", None)
                reasoning_content = getattr(message, "reasoning_content", "")

                final_content = ""
                if enable_cot:
                    if reasoning_content and reasoning_content.strip():
                        if not content or content.strip() == "":
                            final_content = content or ""
                            if r"\u" in reasoning_content:
                                reasoning_content = safe_unicode_decode(
                                    reasoning_content.encode("utf-8")
                                )
                            final_content = (
                                f"<think>{reasoning_content}</think>{final_content}"
                            )
                        else:
                            final_content = content
                    else:
                        final_content = content or ""
                else:
                    final_content = content or ""

                if not final_content or final_content.strip() == "":
                    await openai_async_client.close()
                    raise InvalidResponseError("Received empty content from OpenAI API")

            if r"\u" in final_content:
                final_content = safe_unicode_decode(final_content.encode("utf-8"))

            if token_tracker and hasattr(response, "usage"):
                token_tracker.add_usage(
                    {
                        "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(
                            response.usage, "completion_tokens", 0
                        ),
                        "total_tokens": getattr(response.usage, "total_tokens", 0),
                    }
                )

            logger.debug(f"Response content len: {len(final_content)}")
            return final_content
        finally:
            await openai_async_client.close()


@wrap_embedding_func_with_attrs(
    embedding_dim=1536, max_token_size=8192, model_name="text-embedding-3-small"
)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=(
        retry_if_exception_type(RateLimitError)
        | retry_if_exception_type(APIConnectionError)
        | retry_if_exception_type(APITimeoutError)
    ),
)
async def openai_embed(
    texts: list[str],
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
    api_key: str | None = None,
    embedding_dim: int | None = None,
    max_token_size: int | None = None,
    client_configs: dict[str, Any] | None = None,
    token_tracker: Any | None = None,
) -> np.ndarray:
    if max_token_size is not None and max_token_size > 0:
        encoding = _get_tiktoken_encoding_for_model(model)
        truncated_texts = []
        truncation_count = 0

        for text in texts:
            if not text:
                truncated_texts.append(text)
                continue
            tokens = encoding.encode(text)
            if len(tokens) > max_token_size:
                truncated_texts.append(encoding.decode(tokens[:max_token_size]))
                truncation_count += 1
            else:
                truncated_texts.append(text)

        if truncation_count > 0:
            logger.info(
                f"Truncated {truncation_count}/{len(texts)} texts to fit token limit ({max_token_size})"
            )
        texts = truncated_texts

    openai_async_client = create_openai_async_client(
        api_key=api_key,
        base_url=base_url,
        client_configs=client_configs,
    )

    async with openai_async_client:
        api_params: dict[str, Any] = {
            "model": model,
            "input": texts,
            "encoding_format": "base64",
        }
        if embedding_dim is not None:
            api_params["dimensions"] = embedding_dim

        response = await openai_async_client.embeddings.create(**api_params)

        if token_tracker and hasattr(response, "usage"):
            token_tracker.add_usage(
                {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }
            )

        return np.array(
            [
                np.array(dp.embedding, dtype=np.float32)
                if isinstance(dp.embedding, list)
                else np.frombuffer(base64.b64decode(dp.embedding), dtype=np.float32)
                for dp in response.data
            ]
        )
