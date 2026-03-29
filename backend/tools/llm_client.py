"""
Unified async LLM client with rate limiting and automatic Groq→Gemini→Ollama fallback.

Prefers **Groq** (OpenAI-compatible chat completions) when `GROQ_API_KEY` is set.
Falls back to **Google Gemini** when only `GEMINI_API_KEY` is set or when Groq rate limits are hit.
Falls back to **Ollama** (local) when both Groq and Gemini fail AND running in development mode.

Rate Limiting Strategy:
- Uses asyncio.Semaphore to limit concurrent LLM calls
- Implements exponential backoff on 429 errors
- Automatically switches to Gemini if Groq is rate-limited
- Falls back to local Ollama as last resort (dev only)
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx
from google import genai
from google.genai import types

from config import get_settings

logger = logging.getLogger(__name__)

_GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT = 120.0

def _is_local_environment() -> bool:
    """Check if running in local development environment."""
    settings = get_settings()
    return settings.debug or settings.ollama_enabled

# Rate limiting: dynamically initialized based on config
_llm_semaphore: asyncio.Semaphore | None = None
_semaphore_lock = asyncio.Lock()

# Track if Groq is currently rate-limited (429 errors)
_groq_rate_limited = False
_groq_rate_limit_lock = asyncio.Lock()
_groq_rate_limit_reset_task: asyncio.Task | None = None

# Track last request time for minimum delay enforcement
_last_request_time: float = 0.0
_last_request_lock = asyncio.Lock()


async def _reset_groq_rate_limit_after_delay(delay_seconds: float = 120.0):
    """Reset the Groq rate limit flag after a cooldown period."""
    global _groq_rate_limited
    await asyncio.sleep(delay_seconds)
    async with _groq_rate_limit_lock:
        _groq_rate_limited = False
        logger.info("Groq rate limit cooldown complete - re-enabling Groq API")


async def _get_semaphore() -> asyncio.Semaphore:
    """Lazy-initialize the semaphore based on config."""
    global _llm_semaphore
    async with _semaphore_lock:
        if _llm_semaphore is None:
            settings = get_settings()
            _llm_semaphore = asyncio.Semaphore(settings.llm_max_concurrent_requests)
        return _llm_semaphore


def _strip_json_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, count=1)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


async def _complete_groq(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
    retry_count: int = 0,
    skip_retries_if_local: bool = False,
) -> tuple[str, bool]:
    """
    Complete using Groq API with retry logic.
    
    In cloud: Retries up to 3 times with exponential backoff on rate limits.
    In local: Skips retries and falls back immediately (when skip_retries_if_local=True).
    
    Returns: (response_text, should_fallback_to_gemini)
    """
    global _groq_rate_limited
    
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    messages: list[dict[str, str]] = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    for model in (settings.groq_model_primary, settings.groq_model_fallback):
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2 if expect_json else 0.3,
            "max_tokens": 16384,  # Increased to prevent truncation
        }
        if expect_json:
            body["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(_GROQ_CHAT_URL, headers=headers, json=body)
                
                # Handle rate limiting (429)
                if r.status_code == 429:
                    global _groq_rate_limit_reset_task
                    
                    async with _groq_rate_limit_lock:
                        _groq_rate_limited = True
                        # Schedule reset after cooldown (cancel existing task if any)
                        if _groq_rate_limit_reset_task and not _groq_rate_limit_reset_task.done():
                            _groq_rate_limit_reset_task.cancel()
                        _groq_rate_limit_reset_task = asyncio.create_task(_reset_groq_rate_limit_after_delay(120.0))
                    
                    # In local env with Ollama available, skip retries and fallback immediately
                    if skip_retries_if_local:
                        logger.warning(f"Groq rate limited (429) - skipping retries in local mode, falling back to Gemini")
                        return "", True  # Signal to fallback to Gemini
                    
                    # Cloud mode: Exponential backoff with retries
                    if retry_count < 3:
                        wait_time = (2 ** retry_count) * 3.0  # 3s, 6s, 12s
                        logger.warning(f"Groq rate limited (429), waiting {wait_time}s before retry {retry_count + 1}")
                        await asyncio.sleep(wait_time)
                        return await _complete_groq(prompt, expect_json, system_instruction, retry_count + 1, skip_retries_if_local)
                    else:
                        logger.error(f"Groq rate limited after {retry_count} retries, falling back to Gemini")
                        return "", True  # Signal to fallback to Gemini
                
                if r.status_code == 400 and expect_json and "response_format" in body:
                    logger.warning(f"Groq model {model}: JSON mode rejected, retrying without response_format")
                    body.pop("response_format", None)
                    r = await client.post(_GROQ_CHAT_URL, headers=headers, json=body)
                
                r.raise_for_status()
                data = r.json()
                
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if expect_json:
                content = _strip_json_fences(content)
            
            # Success - reset rate limit flag
            async with _groq_rate_limit_lock:
                _groq_rate_limited = False
            
            return content, False
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Already handled above, but catch it here too
                logger.warning(f"Groq model {model} rate limited: {e}")
                continue
            logger.warning(f"Groq model {model} failed: {e}")
            continue
        except Exception as e:
            logger.warning(f"Groq model {model} failed: {e}")
            continue

    logger.error("Groq: all models failed")
    return "", True  # Fallback to Gemini


async def _complete_gemini(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
    retry_count: int = 0,
    skip_retries_if_local: bool = False,
) -> str:
    """
    Complete using Gemini API with retry logic.
    
    In cloud: Retries up to 3 times with exponential backoff on rate limits.
    In local: Skips retries and falls back immediately (when skip_retries_if_local=True).
    """
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    for model in (settings.gemini_model_primary, settings.gemini_model_fallback):
        try:
            base_kw: dict[str, Any] = {
                "temperature": 0.2 if expect_json else 0.3,
                "max_output_tokens": 8192,  # Increased to prevent truncation
            }
            if expect_json:
                base_kw["response_mime_type"] = "application/json"
            if system_instruction:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    **base_kw,
                )
            else:
                config = types.GenerateContentConfig(**base_kw)

            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            # Check for rate limiting in Gemini
            if "429" in str(e) or "quota" in str(e).lower() or "rate" in str(e).lower() or "RESOURCE_EXHAUSTED" in str(e):
                # In local env with Ollama available, skip retries and fallback immediately
                if skip_retries_if_local:
                    logger.warning(f"Gemini rate limited - skipping retries in local mode, will fallback to Ollama")
                    # Don't retry, just fail and let caller handle Ollama fallback
                    logger.error("Gemini: all models failed")
                    return ""
                
                # Cloud mode: Exponential backoff with retries
                if retry_count < 3:
                    wait_time = (2 ** retry_count) * 5.0  # 5s, 10s, 20s
                    logger.warning(f"Gemini rate limited, waiting {wait_time}s before retry {retry_count + 1}")
                    await asyncio.sleep(wait_time)
                    return await _complete_gemini(prompt, expect_json, system_instruction, retry_count + 1, skip_retries_if_local)
            
            logger.warning(f"Gemini model {model} failed: {e}")
            continue

    logger.error("Gemini: all models failed")
    return ""


async def _complete_ollama(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
) -> str:
    """
    Complete using Ollama (local) API as final fallback.
    Only used in local development when both Groq and Gemini fail.
    """
    settings = get_settings()
    
    if not settings.ollama_enabled:
        logger.debug("Ollama not enabled, skipping")
        return ""
    
    if not _is_local_environment():
        logger.debug("Not in local environment, skipping Ollama")
        return ""
    
    try:
        # Build messages array
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        # Ollama uses OpenAI-compatible API
        url = f"{settings.ollama_base_url}/v1/chat/completions"
        
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
            response = await client.post(url, json=body)
            response.raise_for_status()
            data = response.json()
            
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if expect_json:
                content = _strip_json_fences(content)
            
            logger.info(f"Ollama completion successful ({len(content)} chars)")
            return content
            
    except httpx.ConnectError:
        logger.warning(
            f"Ollama not running at {settings.ollama_base_url}. "
            "Start Ollama with: ollama serve"
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
    priority: int = 5,  # 1=highest (extraction), 5=normal (outputs), 10=lowest
) -> str:
    """
    Run a completion with rate limiting and automatic fallback chain.
    
    Fallback order:
    1. Groq (if GROQ_API_KEY is set and not rate-limited)
    2. Gemini (if GEMINI_API_KEY is set)
    3. Ollama (if OLLAMA_ENABLED=true and running locally in dev mode)
    
    Priority levels (lower = higher priority):
      1 = Critical (extraction, root cause classification)
      2 = High (root cause classification)
      3 = High (appeal letters)
      4 = High (action checklists)
      5 = Normal (summaries)
      6 = Lower (provider briefs)
      7 = Lower (routing cards)
      10 = Low priority (optional enhancements)
    
    Rate limiting: Configurable max concurrent LLM calls via semaphore (default: 1).
    """
    global _groq_rate_limited
    
    settings = get_settings()
    semaphore = await _get_semaphore()
    
    # Acquire semaphore to limit concurrent calls
    async with semaphore:
        # Enforce minimum delay between requests to respect rate limits
        global _last_request_time
        async with _last_request_lock:
            import time
            now = time.time()
            time_since_last = now - _last_request_time
            min_delay = settings.llm_min_delay_between_requests
            
            if time_since_last < min_delay:
                wait_time = min_delay - time_since_last
                logger.debug(f"Rate limit: waiting {wait_time:.1f}s before next request")
                await asyncio.sleep(wait_time)
            
            _last_request_time = time.time()
        
        # Add additional delay based on priority to serialize calls
        # Higher priority calls go first with minimal additional delay
        if priority > 1:
            await asyncio.sleep(0.5 * (priority - 1))  # 0.5s, 1s, 1.5s, 2s, 2.5s, 3s delays
        
        # Check if we should skip retries (local env with Ollama available)
        skip_retries = _is_local_environment() and settings.ollama_enabled
        
        # Check if Groq is currently rate-limited
        should_skip_groq = False
        async with _groq_rate_limit_lock:
            should_skip_groq = _groq_rate_limited
        
        # Try Groq first (unless rate-limited or no key)
        if settings.groq_api_key and not should_skip_groq:
            logger.debug(f"Attempting Groq completion (priority={priority})")
            response, should_fallback = await _complete_groq(prompt, expect_json, system_instruction, 0, skip_retries)
            
            if response:
                return response
            
            # If Groq failed with rate limit signal, try Gemini
            if should_fallback and settings.gemini_api_key:
                logger.info("Groq failed/rate-limited, falling back to Gemini")
                gemini_response = await _complete_gemini(prompt, expect_json, system_instruction, 0, skip_retries)
                
                if gemini_response:
                    return gemini_response
                
                # If Gemini also failed, try Ollama as last resort (local only)
                if _is_local_environment() and settings.ollama_enabled:
                    logger.info("Gemini failed, falling back to Ollama (local)")
                    return await _complete_ollama(prompt, expect_json, system_instruction)
                
                return gemini_response  # Empty string
            
            # If Groq failed but no Gemini key, try Ollama (local only)
            if _is_local_environment() and settings.ollama_enabled:
                logger.info("Groq failed and no Gemini key, falling back to Ollama (local)")
                return await _complete_ollama(prompt, expect_json, system_instruction)
            
            return response  # Empty string if no fallback available
        
        # Use Gemini if Groq is rate-limited or not configured
        if settings.gemini_api_key:
            if should_skip_groq:
                logger.info("Groq currently rate-limited, using Gemini directly")
            logger.debug(f"Attempting Gemini completion (priority={priority})")
            gemini_response = await _complete_gemini(prompt, expect_json, system_instruction, 0, skip_retries)
            
            if gemini_response:
                return gemini_response
            
            # If Gemini failed, try Ollama as last resort (local only)
            if _is_local_environment() and settings.ollama_enabled:
                logger.info("Gemini failed, falling back to Ollama (local)")
                return await _complete_ollama(prompt, expect_json, system_instruction)
            
            return gemini_response  # Empty string
        
        # No cloud API keys configured, try Ollama (local only)
        if _is_local_environment() and settings.ollama_enabled:
            logger.info("No cloud API keys configured, using Ollama (local)")
            return await _complete_ollama(prompt, expect_json, system_instruction)
        
        logger.warning("No LLM API key configured — set GROQ_API_KEY (preferred) or GEMINI_API_KEY, or enable Ollama for local development")
        return ""


async def reset_groq_rate_limit():
    """Manually reset the Groq rate limit flag (useful for testing or manual recovery)."""
    global _groq_rate_limited
    async with _groq_rate_limit_lock:
        _groq_rate_limited = False
        logger.info("Groq rate limit flag manually reset")


def is_groq_rate_limited() -> bool:
    """Check if Groq is currently marked as rate-limited."""
    return _groq_rate_limited
