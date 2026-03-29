"""
Unified async LLM client.

Prefers **Groq** (OpenAI-compatible chat completions) when `GROQ_API_KEY` is set.
Falls back to **Google Gemini** when only `GEMINI_API_KEY` is set.
"""
from __future__ import annotations

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
) -> str:
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
            "max_tokens": 8192,
        }
        if expect_json:
            body["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.post(_GROQ_CHAT_URL, headers=headers, json=body)
                if r.status_code == 400 and expect_json and "response_format" in body:
                    logger.warning(f"Groq model {model}: JSON mode rejected, retrying without response_format")
                    body.pop("response_format", None)
                    r = await client.post(_GROQ_CHAT_URL, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if expect_json:
                content = _strip_json_fences(content)
            return content
        except Exception as e:
            logger.warning(f"Groq model {model} failed: {e}")
            continue

    logger.error("Groq: all models failed")
    return ""


async def _complete_gemini(
    prompt: str,
    expect_json: bool,
    system_instruction: str | None,
) -> str:
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    for model in (settings.gemini_model_primary, settings.gemini_model_fallback):
        try:
            base_kw: dict[str, Any] = {
                "temperature": 0.2 if expect_json else 0.3,
                "max_output_tokens": 4096,
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
            logger.warning(f"Gemini model {model} failed: {e}")
            continue

    logger.error("Gemini: all models failed")
    return ""


async def complete_llm(
    prompt: str,
    *,
    expect_json: bool = False,
    system_instruction: str | None = None,
) -> str:
    """
    Run a completion. Uses Groq if `GROQ_API_KEY` is set, else Gemini if `GEMINI_API_KEY` is set.
    """
    settings = get_settings()
    if settings.groq_api_key:
        return await _complete_groq(prompt, expect_json, system_instruction)
    if settings.gemini_api_key:
        return await _complete_gemini(prompt, expect_json, system_instruction)
    logger.warning("No LLM API key configured — set GROQ_API_KEY (preferred) or GEMINI_API_KEY")
    return ""
