"""
llm_analysis.py
---------------
Unified LLM client for Module 2 analysis services.

Rotates across TWO provider pools:
  Pool A — Groq  (GROQ_API_KEY1..5)  → llama-3.3-70b-versatile
  Pool B — Gemini (GEMINI_API_KEY1..5) → gemini-2.0-flash

Round-robin strategy:
  1. Try the next Groq key.
  2. If all Groq keys fail, try the next Gemini key.
  3. Repeat up to `retries` total attempts.

Completely separate from OpenRouter / llm_router used in CV extraction.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key loading
# ---------------------------------------------------------------------------
_GROQ_KEYS: list[str] = [
    v for k, v in sorted(os.environ.items())
    if k.startswith("GROQ_API_KEY") and v.strip()
]

_GEMINI_KEYS: list[str] = [
    v for k, v in sorted(os.environ.items())
    if k.startswith("GEMINI_API_KEY") and v.strip()
]

if not _GROQ_KEYS:
    logger.warning("No GROQ_API_KEY* found — Groq calls will be skipped.")
if not _GEMINI_KEYS:
    logger.warning("No GEMINI_API_KEY* found — Gemini calls will be skipped.")

logger.info(
    "LLM Analysis pool initialized | Groq keys: %d | Gemini keys: %d",
    len(_GROQ_KEYS), len(_GEMINI_KEYS),
)

# Thread-safe key cycles
_lock = threading.Lock()
_groq_cycle = itertools.cycle(_GROQ_KEYS) if _GROQ_KEYS else None
_gemini_cycle = itertools.cycle(_GEMINI_KEYS) if _GEMINI_KEYS else None

# Models
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_FAST_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.0-flash"

# Stats
_stats = {
    "groq_attempts": 0, "groq_successes": 0, "groq_failures": 0,
    "gemini_attempts": 0, "gemini_successes": 0, "gemini_failures": 0,
    "last_provider": None, "last_error": None,
}


def _next_groq_key() -> str | None:
    if not _groq_cycle:
        return None
    with _lock:
        return next(_groq_cycle, None)


def _next_gemini_key() -> str | None:
    if not _gemini_cycle:
        return None
    with _lock:
        return next(_gemini_cycle, None)


# ---------------------------------------------------------------------------
# Groq call
# ---------------------------------------------------------------------------
def _call_groq(
    system_prompt: str,
    user_prompt: str,
    key: str,
    *,
    model: str = GROQ_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    json_mode: bool = True,
) -> dict[str, Any] | str | None:
    """Make a single Groq call. Returns parsed dict (json_mode=True) or str."""
    from groq import Groq

    client = Groq(api_key=key)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""
    raw = raw.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[-1].lstrip("json").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    if json_mode:
        return json.loads(raw)
    return raw


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------
def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    key: str,
    *,
    model: str = GEMINI_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    json_mode: bool = True,
) -> dict[str, Any] | str | None:
    """Make a single Gemini call via google-generativeai SDK."""
    import google.generativeai as genai

    genai.configure(api_key=key)

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    gmodel = genai.GenerativeModel(
        model_name=model,
        generation_config=generation_config,
        system_instruction=system_prompt,
    )

    response = gmodel.generate_content(user_prompt)
    raw = response.text or ""
    raw = raw.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[-1].lstrip("json").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    if json_mode:
        return json.loads(raw)
    return raw


# ---------------------------------------------------------------------------
# Unified call with rotation
# ---------------------------------------------------------------------------
def analysis_llm_call(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    json_mode: bool = True,
    retries: int = 4,
) -> dict[str, Any] | str | None:
    """
    Make an LLM call for analysis tasks, rotating across Groq and Gemini keys.

    Strategy: try Groq first (faster, larger context), fall back to Gemini.
    Round-robin across all keys until success or exhaustion.

    Returns:
        Parsed JSON dict (json_mode=True) or plain string (json_mode=False).
        None on total failure.
    """
    if os.getenv("TALASH_DISABLE_ANALYSIS_LLM", "").strip().lower() in {"1", "true", "yes"}:
        logger.info("[LLM-ANALYSIS] Disabled via TALASH_DISABLE_ANALYSIS_LLM=1")
        return None
    if os.getenv("TALASH_REUSE_STORED_EXTRACTION", "").strip().lower() in {"1", "true", "yes"}:
        logger.info("[LLM-ANALYSIS] Disabled via TALASH_REUSE_STORED_EXTRACTION=1 (offline rerun)")
        return None

    last_err: Exception | None = None

    for attempt in range(retries):
        # Alternate: even attempts → Groq, odd attempts → Gemini
        # But if one pool is empty, use the other
        if attempt % 2 == 0 and _GROQ_KEYS:
            provider = "groq"
        elif _GEMINI_KEYS:
            provider = "gemini"
        elif _GROQ_KEYS:
            provider = "groq"
        else:
            logger.error("No LLM keys available for analysis.")
            return None

        try:
            if provider == "groq":
                key = _next_groq_key()
                if not key:
                    continue
                _stats["groq_attempts"] += 1
                result = _call_groq(
                    system_prompt, user_prompt, key,
                    max_tokens=max_tokens, temperature=temperature,
                    json_mode=json_mode,
                )
                _stats["groq_successes"] += 1
                _stats["last_provider"] = "groq"
                logger.info(
                    "[LLM-ANALYSIS] Groq call succeeded (attempt %d/%d)",
                    attempt + 1, retries,
                )
                return result

            else:  # gemini
                key = _next_gemini_key()
                if not key:
                    continue
                _stats["gemini_attempts"] += 1
                result = _call_gemini(
                    system_prompt, user_prompt, key,
                    max_tokens=max_tokens, temperature=temperature,
                    json_mode=json_mode,
                )
                _stats["gemini_successes"] += 1
                _stats["last_provider"] = "gemini"
                logger.info(
                    "[LLM-ANALYSIS] Gemini call succeeded (attempt %d/%d)",
                    attempt + 1, retries,
                )
                return result

        except Exception as exc:
            last_err = exc
            if provider == "groq":
                _stats["groq_failures"] += 1
            else:
                _stats["gemini_failures"] += 1
            _stats["last_error"] = str(exc)[:500]
            logger.warning(
                "[LLM-ANALYSIS] %s call attempt %d/%d failed: %s",
                provider.upper(), attempt + 1, retries, exc,
            )
            if attempt < retries - 1:
                time.sleep(min(2 ** attempt, 8))

    logger.error("All analysis LLM retries exhausted. Last error: %s", last_err)
    return None


def analysis_text_call(
    system_prompt: str,
    user_prompt: str,
    *,
    max_tokens: int = 2048,
) -> str | None:
    """Plain text LLM call for narrative summaries."""
    result = analysis_llm_call(
        system_prompt, user_prompt,
        max_tokens=max_tokens, temperature=0.3,
        json_mode=False, retries=3,
    )
    if isinstance(result, str):
        return result
    return None


def get_analysis_stats() -> dict:
    """Return rotation stats for observability."""
    return dict(_stats)
