"""
llm_groq.py
-----------
Direct Groq client for Module 2 analysis services.
Uses round-robin rotation across GROQ_API_KEY1..5.
Completely separate from OpenRouter / llm_router used in CV extraction.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import time
from typing import Any

from groq import Groq

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key rotation
# ---------------------------------------------------------------------------
_GROQ_KEYS: list[str] = [
    v for k, v in sorted(os.environ.items())
    if k.startswith("GROQ_API_KEY") and v.strip()
]

if not _GROQ_KEYS:
    logger.warning("No GROQ_API_KEY* found in environment — Groq LLM calls will fail.")

_key_cycle = itertools.cycle(_GROQ_KEYS) if _GROQ_KEYS else iter([])

DEFAULT_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL    = "llama-3.1-8b-instant"       # fallback for simple tasks


# ---------------------------------------------------------------------------
# Core call
# ---------------------------------------------------------------------------
def groq_json_call(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    retries: int = 3,
) -> dict[str, Any] | None:
    """
    Make a Groq chat call and return parsed JSON dict.
    Rotates keys on each attempt. Returns None on total failure.

    The system prompt MUST instruct the model to return only JSON.
    """
    last_err: Exception | None = None
    for attempt in range(retries):
        key = next(_key_cycle, None)
        if not key:
            logger.error("No Groq API keys available.")
            return None
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            # Strip accidental markdown fences
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```", 2)[-1].lstrip("json").strip()
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
            return json.loads(raw)
        except Exception as exc:
            last_err = exc
            logger.warning(
                "Groq call attempt %d/%d failed (key index rotating): %s",
                attempt + 1, retries, exc,
            )
            if attempt < retries - 1:
                time.sleep(2 ** attempt)   # 1s, 2s backoff

    logger.error("All Groq retries exhausted. Last error: %s", last_err)
    return None


def groq_text_call(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
) -> str | None:
    """Plain text Groq call — for narrative summaries."""
    key = next(_key_cycle, None)
    if not key:
        return None
    try:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("Groq text call failed: %s", exc)
        return None
