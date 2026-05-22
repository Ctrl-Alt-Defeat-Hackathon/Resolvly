"""
Unified async LLM client with rate limiting and OpenAI → Ollama fallback.

Uses **OpenAI** chat completions when `OPENAI_API_KEY` is set.
Falls back to **Ollama** (local) when OpenAI fails and running in development mode.

Rate limiting:
- asyncio.Semaphore limits concurrent LLM calls
- Exponential backoff on 429 errors
- Cooldown flag to skip OpenAI briefly after rate limits
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = 120.0


def _openai_chat_url() -> str:
    settings = get_settings()
    base = (settings.openai_base_url or "").strip().rstrip("/")
    if not base:
        return _DEFAULT_OPENAI_CHAT_URL
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _is_local_environment() -> bool:
    settings = get_settings()
    return settings.debug or settings.ollama_enabled


_openai_rate_limited = False
_openai_rate_limit_lock = asyncio.Lock()
_openai_rate_limit_reset_task: asyncio.Task | None = None

_last_request_time: float = 0.0
_last_request_lock = asyncio.Lock()

# Priority queue-based dispatch — replaces the Semaphore + sleep approach.
# Workers dequeue by (priority, seq) so lower priority numbers run first.
# _request_seq breaks FIFO ties within the same priority level.
_llm_request_queue: asyncio.PriorityQueue | None = None
_llm_worker_tasks: list[asyncio.Task] = []
_worker_init_lock = asyncio.Lock()
_request_seq: int = 0


async def _reset_openai_rate_limit_after_delay(delay_seconds: float = 120.0):
    global _openai_rate_limited
    await asyncio.sleep(delay_seconds)
    async with _openai_rate_limit_lock:
        _openai_rate_limited = False
        logger.info("OpenAI rate limit cooldown complete — re-enabling OpenAI API")


async def _execute_llm_call(prompt: str, expect_json: bool, system_instruction: str | None) -> str:
    """
    Execute a single LLM call with rate limiting and fallback.
    Called exclusively by _llm_worker_loop — never directly.
    """
    global _last_request_time, _openai_rate_limited

    async with _last_request_lock:
        now = time.time()
        time_since_last = now - _last_request_time
        settings = get_settings()
        min_delay = settings.llm_min_delay_between_requests
        if time_since_last < min_delay:
            wait_time = min_delay - time_since_last
            logger.debug(f"Rate limit: waiting {wait_time:.1f}s before next request")
            await asyncio.sleep(wait_time)
        _last_request_time = time.time()

    settings = get_settings()
    skip_retries = _is_local_environment() and settings.ollama_enabled

    should_skip_openai = False
    async with _openai_rate_limit_lock:
        should_skip_openai = _openai_rate_limited

    if settings.openai_api_key and not should_skip_openai:
        response, should_fallback = await _complete_openai(
            prompt, expect_json, system_instruction, 0, skip_retries
        )
        if response:
            return response
        if _is_local_environment() and settings.ollama_enabled:
            logger.info("OpenAI failed, falling back to Ollama (local)")
            return await _complete_ollama(prompt, expect_json, system_instruction)
        return response

    if should_skip_openai:
        logger.info("OpenAI currently rate-limited")

    if _is_local_environment() and settings.ollama_enabled:
        logger.info("Using Ollama (local)")
        return await _complete_ollama(prompt, expect_json, system_instruction)

    logger.warning(
        "No LLM API key configured — set OPENAI_API_KEY, or enable Ollama for local development"
    )
    return ""


async def _llm_worker_loop():
    """Single worker that dequeues and processes LLM requests in priority order."""
    while True:
        item = await _llm_request_queue.get()
        _priority, _seq, prompt, expect_json, system_instruction, future = item
        try:
            result = await _execute_llm_call(prompt, expect_json, system_instruction)
            if not future.done():
                future.set_result(result)
        except Exception as e:
            if not future.done():
                future.set_exception(e)
        finally:
            _llm_request_queue.task_done()


async def _ensure_workers():
    """Lazily initialize the priority queue and worker pool (called from async context)."""
    global _llm_request_queue, _llm_worker_tasks
    async with _worker_init_lock:
        if _llm_request_queue is None:
            settings = get_settings()
            _llm_request_queue = asyncio.PriorityQueue()
            _llm_worker_tasks = [
                asyncio.create_task(_llm_worker_loop())
                for _ in range(settings.llm_max_concurrent_requests)
            ]
            logger.info(
                f"LLM worker pool started: {settings.llm_max_concurrent_requests} workers, "
                "priority queue active"
            )


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, count=1)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _extract_json_block(text: str) -> str:
    t = text.strip()
    if not t:
        return t

    obj_start = t.find("{")
    obj_end = t.rfind("}")
    arr_start = t.find("[")
    arr_end = t.rfind("]")

    obj_candidate = ""
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        obj_candidate = t[obj_start : obj_end + 1]

    arr_candidate = ""
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        arr_candidate = t[arr_start : arr_end + 1]

    if obj_candidate and arr_candidate:
        return obj_candidate if len(obj_candidate) >= len(arr_candidate) else arr_candidate
    return obj_candidate or arr_candidate or t


async def _complete_openai(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
    retry_count: int = 0,
    skip_retries_if_local: bool = False,
) -> tuple[str, bool]:
    """
    Complete using OpenAI chat completions API.

    Returns: (response_text, hit_rate_limit_or_hard_failure)
    """
    global _openai_rate_limited, _openai_rate_limit_reset_task

    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    url = _openai_chat_url()

    for model in (settings.openai_model_primary, settings.openai_model_fallback):
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2 if expect_json else 0.3,
            "max_tokens": 16384,
        }
        if expect_json:
            body["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(url, headers=headers, json=body)

                if r.status_code == 429:
                    async with _openai_rate_limit_lock:
                        _openai_rate_limited = True
                        if _openai_rate_limit_reset_task and not _openai_rate_limit_reset_task.done():
                            _openai_rate_limit_reset_task.cancel()
                        _openai_rate_limit_reset_task = asyncio.create_task(
                            _reset_openai_rate_limit_after_delay(120.0)
                        )

                    if skip_retries_if_local:
                        logger.warning("OpenAI rate limited (429) — falling back to Ollama")
                        return "", True

                    if retry_count < 3 and settings.llm_retry_on_rate_limit:
                        wait_time = (2 ** retry_count) * 3.0
                        logger.warning(
                            f"OpenAI rate limited (429), waiting {wait_time}s before retry {retry_count + 1}"
                        )
                        await asyncio.sleep(wait_time)
                        return await _complete_openai(
                            prompt, expect_json, system_instruction, retry_count + 1, skip_retries_if_local
                        )

                    logger.error(f"OpenAI rate limited after {retry_count} retries")
                    return "", True

                if r.status_code == 400 and expect_json and "response_format" in body:
                    logger.warning(f"OpenAI model {model}: JSON mode rejected, retrying without response_format")
                    body.pop("response_format", None)
                    r = await client.post(url, headers=headers, json=body)

                r.raise_for_status()
                data = r.json()

            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if expect_json:
                content = _strip_json_fences(content)

            async with _openai_rate_limit_lock:
                _openai_rate_limited = False

            return content, False

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"OpenAI model {model} rate limited: {e}")
                continue
            logger.warning(f"OpenAI model {model} failed: {e}")
            continue
        except Exception as e:
            logger.warning(f"OpenAI model {model} failed: {e}")
            continue

    logger.error("OpenAI: all models failed")
    return "", True


async def _complete_ollama(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
) -> str:
    settings = get_settings()

    if not settings.ollama_enabled:
        logger.debug("Ollama not enabled, skipping")
        return ""

    if not _is_local_environment():
        logger.debug("Not in local environment, skipping Ollama")
        return ""

    try:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        ollama_url = f"{settings.ollama_base_url.rstrip('/')}/v1/chat/completions"
        body: dict[str, Any] = {
            "model": settings.ollama_model,
            "messages": messages,
            "temperature": 0.2 if expect_json else 0.3,
            "stream": False,
        }
        if expect_json:
            body["format"] = "json"

        logger.info(f"Attempting Ollama completion with model {settings.ollama_model}")

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(ollama_url, json=body)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if expect_json:
                content = _strip_json_fences(content)
                content = _extract_json_block(content)

            logger.info(f"Ollama completion successful ({len(content)} chars)")
            return content

    except httpx.ConnectError:
        logger.warning(
            f"Ollama not running at {settings.ollama_base_url}. Start with: ollama serve"
        )
        return ""
    except Exception as e:
        logger.warning(f"Ollama completion failed: {e}")
        return ""


async def complete_llm(
    prompt: str,
    *,
    expect_json: bool = False,
    system_instruction: str | None = None,
    priority: int = 5,
) -> str:
    """
    Enqueue an LLM completion request and await the result.

    Requests are processed by a worker pool in priority order:
      priority=1 (highest) → extraction, root cause classification
      priority=8 (lowest)  → appeal letter generation

    Workers execute requests in (priority, arrival_order) order, so a
    priority=1 request always runs before a queued priority=8 request,
    regardless of arrival time.

    Fallback order per worker:
      1. OpenAI (if OPENAI_API_KEY is set and not rate-limited)
      2. Ollama (if OLLAMA_ENABLED=true and running locally)
    """
    global _request_seq

    await _ensure_workers()

    loop = asyncio.get_event_loop()
    future: asyncio.Future[str] = loop.create_future()
    _request_seq += 1
    seq = _request_seq

    logger.debug(f"LLM request enqueued (priority={priority}, seq={seq})")
    await _llm_request_queue.put((priority, seq, prompt, expect_json, system_instruction, future))
    return await future


async def reset_openai_rate_limit():
    """Manually reset the OpenAI rate limit flag."""
    global _openai_rate_limited
    async with _openai_rate_limit_lock:
        _openai_rate_limited = False
        logger.info("OpenAI rate limit flag manually reset")


def is_openai_rate_limited() -> bool:
    return _openai_rate_limited


# Backward-compatible aliases (deprecated)
reset_groq_rate_limit = reset_openai_rate_limit
is_groq_rate_limited = is_openai_rate_limited
