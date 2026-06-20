from __future__ import annotations

import os
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

import numpy as np
import pipmaster as pm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from rag.utils import (
    logger,
    remove_think_tags,
    safe_unicode_decode,
    wrap_embedding_func_with_attrs,
)

# Install the Google Gemini client on demand
if not pm.is_installed("google-genai"):
    pm.install("google-genai")
if not pm.is_installed("google-api-core"):
    pm.install("google-api-core")

from google import genai  # type: ignore
from google.genai import types  # type: ignore
from google.api_core import exceptions as google_api_exceptions  # type: ignore


class InvalidResponseError(Exception):
    """Custom exception class for triggering retry mechanism"""

    pass


@lru_cache(maxsize=8)
def _get_gemini_client(
    api_key: str, base_url: str | None, timeout: int | None = None
) -> genai.Client:
    """Create (or fetch cached) Gemini client."""
    client_kwargs: dict[str, Any] = {"api_key": api_key}

    if base_url or timeout is not None:
        http_options_kwargs = {}
        if base_url:
            http_options_kwargs["base_url"] = base_url
        if timeout is not None:
            http_options_kwargs["timeout"] = timeout
        client_kwargs["http_options"] = types.HttpOptions(**http_options_kwargs)

    return genai.Client(**client_kwargs)


def _ensure_api_key(api_key: str | None) -> str:
    key = api_key or os.getenv("LLM_BINDING_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "Gemini API key not provided. "
            "Set LLM_BINDING_API_KEY or GEMINI_API_KEY in the environment."
        )
    return key


def _build_generation_config(
    base_config: dict[str, Any] | None,
    system_prompt: str | None,
    keyword_extraction: bool,
) -> types.GenerateContentConfig | None:
    config_data = dict(base_config or {})

    if system_prompt:
        if config_data.get("system_instruction"):
            config_data["system_instruction"] = (
                f"{config_data['system_instruction']}\n{system_prompt}"
            )
        else:
            config_data["system_instruction"] = system_prompt

    if keyword_extraction and not config_data.get("response_mime_type"):
        config_data["response_mime_type"] = "application/json"

    sanitized = {k: v for k, v in config_data.items() if v is not None and v != ""}
    if not sanitized:
        return None

    return types.GenerateContentConfig(**sanitized)


def _format_history_messages(history_messages: list[dict[str, Any]] | None) -> str:
    if not history_messages:
        return ""
    return "\n".join(
        f"[{msg.get('role', 'user')}] {msg.get('content', '')}"
        for msg in history_messages
    )


def _extract_response_text(
    response: Any, extract_thoughts: bool = False
) -> tuple[str, str]:
    """Extract text content from Gemini response, separating content from thoughts."""
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return ("", "")

    regular_parts: list[str] = []
    thought_parts: list[str] = []

    for candidate in candidates:
        if not getattr(candidate, "content", None):
            continue
        for part in getattr(candidate.content, "parts", None) or []:
            text = getattr(part, "text", None)
            if not text:
                continue
            is_thought = getattr(part, "thought", False)
            if is_thought and extract_thoughts:
                thought_parts.append(text)
            elif not is_thought:
                regular_parts.append(text)

    return ("\n".join(regular_parts), "\n".join(thought_parts))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=(
        retry_if_exception_type(google_api_exceptions.InternalServerError)
        | retry_if_exception_type(google_api_exceptions.ServiceUnavailable)
        | retry_if_exception_type(google_api_exceptions.ResourceExhausted)
        | retry_if_exception_type(google_api_exceptions.GatewayTimeout)
        | retry_if_exception_type(google_api_exceptions.BadGateway)
        | retry_if_exception_type(google_api_exceptions.DeadlineExceeded)
        | retry_if_exception_type(google_api_exceptions.Aborted)
        | retry_if_exception_type(google_api_exceptions.Unknown)
        | retry_if_exception_type(InvalidResponseError)
    ),
)
async def gemini_complete_if_cache(
    model: str,
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, Any]] | None = None,
    enable_cot: bool = False,
    base_url: str | None = None,
    api_key: str | None = None,
    token_tracker: Any | None = None,
    stream: bool | None = None,
    keyword_extraction: bool = False,
    generation_config: dict[str, Any] | None = None,
    timeout: int | None = None,
    **_: Any,
) -> str | AsyncIterator[str]:
    key = _ensure_api_key(api_key)
    timeout_ms = timeout * 1000 if timeout else None
    client = _get_gemini_client(key, base_url, timeout_ms)

    history_block = _format_history_messages(history_messages)
    prompt_sections = []
    if history_block:
        prompt_sections.append(history_block)
    prompt_sections.append(f"[user] {prompt}")
    combined_prompt = "\n".join(prompt_sections)

    config_obj = _build_generation_config(
        generation_config,
        system_prompt=system_prompt,
        keyword_extraction=keyword_extraction,
    )

    request_kwargs: dict[str, Any] = {
        "model": model,
        "contents": [combined_prompt],
    }
    if config_obj is not None:
        request_kwargs["config"] = config_obj

    # --- Streaming ---
    if stream:

        async def _async_stream() -> AsyncIterator[str]:
            cot_active = False
            cot_started = False
            initial_content_seen = False
            usage_metadata = None

            try:
                stream_response = await client.aio.models.generate_content_stream(
                    **request_kwargs
                )
                async for chunk in stream_response:
                    usage = getattr(chunk, "usage_metadata", None)
                    if usage is not None:
                        usage_metadata = usage

                    regular_text, thought_text = _extract_response_text(
                        chunk, extract_thoughts=True
                    )

                    if enable_cot:
                        if regular_text:
                            if not initial_content_seen:
                                initial_content_seen = True
                            if cot_active:
                                yield "</think>"
                                cot_active = False
                            if "\\u" in regular_text:
                                regular_text = safe_unicode_decode(
                                    regular_text.encode("utf-8")
                                )
                            yield regular_text

                        if thought_text:
                            if not initial_content_seen and not cot_started:
                                yield "<think>"
                                cot_active = True
                                cot_started = True
                            if cot_active:
                                if "\\u" in thought_text:
                                    thought_text = safe_unicode_decode(
                                        thought_text.encode("utf-8")
                                    )
                                yield thought_text
                    else:
                        if regular_text:
                            if "\\u" in regular_text:
                                regular_text = safe_unicode_decode(
                                    regular_text.encode("utf-8")
                                )
                            yield regular_text

                if cot_active:
                    yield "</think>"

            except Exception as exc:
                if cot_active:
                    try:
                        yield "</think>"
                    except Exception:
                        pass
                raise exc
            finally:
                if token_tracker and usage_metadata:
                    token_tracker.add_usage(
                        {
                            "prompt_tokens": getattr(
                                usage_metadata, "prompt_token_count", 0
                            ),
                            "completion_tokens": getattr(
                                usage_metadata, "candidates_token_count", 0
                            ),
                            "total_tokens": getattr(
                                usage_metadata, "total_token_count", 0
                            ),
                        }
                    )

        return _async_stream()

    # --- Non-streaming ---
    response = await client.aio.models.generate_content(**request_kwargs)

    regular_text, thought_text = _extract_response_text(response, extract_thoughts=True)

    if enable_cot:
        if thought_text and thought_text.strip():
            if not regular_text or regular_text.strip() == "":
                final_text = f"<think>{thought_text}</think>"
            else:
                final_text = f"<think>{thought_text}</think>{regular_text}"
        else:
            final_text = regular_text or ""
    else:
        final_text = regular_text or ""

    if not final_text:
        raise InvalidResponseError("Gemini response did not contain any text content.")

    if "\\u" in final_text:
        final_text = safe_unicode_decode(final_text.encode("utf-8"))

    final_text = remove_think_tags(final_text)

    usage = getattr(response, "usage_metadata", None)
    if token_tracker and usage:
        token_tracker.add_usage(
            {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                "completion_tokens": getattr(usage, "candidates_token_count", 0),
                "total_tokens": getattr(usage, "total_token_count", 0),
            }
        )

    logger.debug("Gemini response length: %s", len(final_text))
    return final_text


async def gemini_model_complete(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list[dict[str, Any]] | None = None,
    keyword_extraction: bool = False,
    **kwargs: Any,
) -> str | AsyncIterator[str]:
    hashing_kv = kwargs.get("hashing_kv")
    model_name = None
    if hashing_kv is not None:
        model_name = hashing_kv.global_config.get("llm_model_name")
    if model_name is None:
        model_name = kwargs.pop("model_name", None)
    if model_name is None:
        raise ValueError("Gemini model name not provided in configuration.")

    return await gemini_complete_if_cache(
        model_name,
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        keyword_extraction=keyword_extraction,
        **kwargs,
    )


@wrap_embedding_func_with_attrs(
    embedding_dim=1536, max_token_size=2048, model_name="gemini-embedding-001"
)
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=(
        retry_if_exception_type(google_api_exceptions.InternalServerError)
        | retry_if_exception_type(google_api_exceptions.ServiceUnavailable)
        | retry_if_exception_type(google_api_exceptions.ResourceExhausted)
        | retry_if_exception_type(google_api_exceptions.GatewayTimeout)
        | retry_if_exception_type(google_api_exceptions.BadGateway)
        | retry_if_exception_type(google_api_exceptions.DeadlineExceeded)
        | retry_if_exception_type(google_api_exceptions.Aborted)
        | retry_if_exception_type(google_api_exceptions.Unknown)
    ),
)
async def gemini_embed(
    texts: list[str],
    model: str = "gemini-embedding-001",
    base_url: str | None = None,
    api_key: str | None = None,
    embedding_dim: int | None = None,
    max_token_size: int | None = None,
    task_type: str = "RETRIEVAL_DOCUMENT",
    timeout: int | None = None,
    token_tracker: Any | None = None,
) -> np.ndarray:
    _ = max_token_size  # Gemini API handles truncation automatically

    key = _ensure_api_key(api_key)
    timeout_ms = timeout * 1000 if timeout else None
    client = _get_gemini_client(key, base_url, timeout_ms)

    config_kwargs: dict[str, Any] = {}
    if task_type:
        config_kwargs["task_type"] = task_type
    if embedding_dim is not None:
        config_kwargs["output_dimensionality"] = embedding_dim

    config_obj = types.EmbedContentConfig(**config_kwargs) if config_kwargs else None

    request_kwargs: dict[str, Any] = {
        "model": model,
        "contents": texts,
    }
    if config_obj is not None:
        request_kwargs["config"] = config_obj

    response = await client.aio.models.embed_content(**request_kwargs)

    if not hasattr(response, "embeddings") or not response.embeddings:
        raise RuntimeError("Gemini response did not contain embeddings.")

    embeddings = np.array(
        [np.array(e.values, dtype=np.float32) for e in response.embeddings]
    )

    # Apply L2 normalization for dimensions < 3072
    if embedding_dim and embedding_dim < 3072:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = embeddings / norms

    if token_tracker and hasattr(response, "usage_metadata"):
        usage = response.usage_metadata
        token_tracker.add_usage(
            {
                "prompt_tokens": getattr(usage, "prompt_token_count", 0),
                "total_tokens": getattr(usage, "total_token_count", 0),
            }
        )

    logger.debug(
        f"Generated {len(embeddings)} Gemini embeddings with dimension {embeddings.shape[1]}"
    )
    return embeddings


__all__ = [
    "gemini_complete_if_cache",
    "gemini_model_complete",
    "gemini_embed",
]
