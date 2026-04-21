"""
LLM Router: OpenRouter Free Tier Integration for TALASH v3.

Replaces the previous LiteLLM key-rotation router with a single OpenRouter
client using the ``openai.OpenAI`` SDK pointed at ``https://openrouter.ai/api/v1``.

The client is wrapped with ``instructor`` (Mode.JSON) to enforce Pydantic
structured outputs on every extraction call.

Uses model ``openrouter/free`` which auto-routes to the best available free
model on OpenRouter's infrastructure.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from copy import deepcopy
from typing import Any, Tuple

import instructor
from openai import OpenAI

logger = logging.getLogger(__name__)

# ============================================================================
# OpenRouter Configuration
# ============================================================================
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_REFERER = "https://github.com/hamdan-ishfaq/TALASHv2"
OPENROUTER_TITLE = "TALASH v3 HR System"


def get_openrouter_client() -> OpenAI:
    """Create an OpenAI-compatible client pointed at OpenRouter's API.

    Uses the ``OPEN_ROUTER_API_KEY`` environment variable (note the
    underscores – matches the user's .env naming convention).

    The ``default_headers`` include the OpenRouter-recommended
    ``HTTP-Referer`` and ``X-Title`` for app attribution on their
    leaderboard.
    """
    api_key = os.getenv("OPEN_ROUTER_API_KEY", "")
    if not api_key:
        logger.warning(
            "OPEN_ROUTER_API_KEY is not set! All LLM extraction calls will fail. "
            "Add it to your .env file."
        )

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        default_headers={
            "HTTP-Referer": OPENROUTER_REFERER,
            "X-Title": OPENROUTER_TITLE,
        },
    )
    return client


# ============================================================================
# LLM Router (OpenRouter Edition)
# ============================================================================

class LLMRouter:
    """Route LLM requests through OpenRouter's free tier.

    This replaces the previous multi-key LiteLLM rotation router with a
    single OpenRouter client.  The stats/logging infrastructure is preserved
    for observability.
    """

    # --- Previous LiteLLM key rotation logic is COMMENTED OUT ---
    # MAX_KEY_ROTATIONS = 5
    # The old _load_env_keys, _create_litellm_router, _ordered_credentials,
    # and _completion_with_logging methods are no longer needed since we use
    # a single OpenRouter API key and the openai SDK directly.

    def __init__(self):
        self.provider = "openrouter"
        self.model = OPENROUTER_MODEL
        self._lock = threading.Lock()
        self._request_sequence = 0

        # --- Create the OpenRouter client ---
        self._raw_client = get_openrouter_client()

        # --- Wrap with instructor for structured Pydantic outputs ---
        self.client = instructor.from_openai(
            self._raw_client,
            mode=instructor.Mode.JSON,
        )

        # --- Stats tracking (simplified – single key) ---
        self._stats = {
            "total_attempts": 0,
            "total_successes": 0,
            "total_failures": 0,
            "by_key": {
                "OPEN_ROUTER_API_KEY": {
                    "provider": "openrouter",
                    "attempts": 0,
                    "successes": 0,
                    "failures": 0,
                    "last_error": None,
                    "last_request_preview": None,
                    "last_response_preview": None,
                },
            },
            "events": [],
        }

        logger.info(
            "LLM Router initialized | provider=openrouter | model=%s | base_url=%s",
            self.model,
            OPENROUTER_BASE_URL,
        )

    # ------------------------------------------------------------------
    # Structured client interface (unchanged signatures)
    # ------------------------------------------------------------------

    def get_structured_client(self) -> Tuple[instructor.Instructor, str]:
        """Return the instructor-wrapped client and the virtual model name.

        Signature matches the previous LiteLLM version so all existing
        call-sites work without modification.
        """
        return self.client, self.model

    def get_raw_client(self) -> Tuple[OpenAI, str]:
        """Return the raw OpenAI client for standard chat completions without Pydantic."""
        return self._raw_client, self.model

    # ------------------------------------------------------------------
    # Stats / observability (preserved from original)
    # ------------------------------------------------------------------

    def record_attempt(self) -> int:
        """Record a new request attempt and return the request ID."""
        with self._lock:
            self._request_sequence += 1
            self._stats["total_attempts"] += 1
            self._stats["by_key"]["OPEN_ROUTER_API_KEY"]["attempts"] += 1
            return self._request_sequence

    def record_success(self, request_id: int, duration: float, response_preview: str = "") -> None:
        """Record a successful response."""
        with self._lock:
            self._stats["total_successes"] += 1
            key_stats = self._stats["by_key"]["OPEN_ROUTER_API_KEY"]
            key_stats["successes"] += 1
            key_stats["last_response_preview"] = response_preview[:1200]
            self._log_event({
                "request_id": request_id,
                "env_name": "OPEN_ROUTER_API_KEY",
                "provider": "openrouter",
                "model": self.model,
                "status": "success",
                "duration_sec": round(duration, 3),
                "response_preview": response_preview[:500],
            })

    def record_failure(self, request_id: int, duration: float, error_text: str) -> None:
        """Record a failed request."""
        with self._lock:
            self._stats["total_failures"] += 1
            key_stats = self._stats["by_key"]["OPEN_ROUTER_API_KEY"]
            key_stats["failures"] += 1
            key_stats["last_error"] = error_text[:500]
            self._log_event({
                "request_id": request_id,
                "env_name": "OPEN_ROUTER_API_KEY",
                "provider": "openrouter",
                "model": self.model,
                "status": "error",
                "duration_sec": round(duration, 3),
                "error": error_text[:500],
            })

    def _log_event(self, record: dict[str, Any]) -> None:
        self._stats["events"].append(record)
        if len(self._stats["events"]) > 100:
            self._stats["events"] = self._stats["events"][-100:]

    def reset_stats(self) -> None:
        with self._lock:
            for key_stats in self._stats["by_key"].values():
                key_stats["attempts"] = 0
                key_stats["successes"] = 0
                key_stats["failures"] = 0
                key_stats["last_error"] = None
                key_stats["last_request_preview"] = None
                key_stats["last_response_preview"] = None
            self._stats["total_attempts"] = 0
            self._stats["total_successes"] = 0
            self._stats["total_failures"] = 0
            self._stats["events"] = []

    def get_stats_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._stats)

    def format_stats_summary(self, title: str = "LLM REQUEST SUMMARY") -> str:
        snapshot = self.get_stats_snapshot()
        lines = [
            "=" * 110,
            f"[{title}]",
            f"Total Attempts: {snapshot['total_attempts']}",
            f"Total Successes: {snapshot['total_successes']}",
            f"Total Failures: {snapshot['total_failures']}",
        ]
        for env_name, stats in snapshot["by_key"].items():
            lines.append(
                f"  - {env_name} | provider={stats['provider']} | attempts={stats['attempts']} | "
                f"successes={stats['successes']} | failures={stats['failures']}"
            )
            if stats.get("last_error"):
                lines.append(f"      last_error={stats['last_error']}")
            if stats.get("last_request_preview"):
                lines.append(f"      last_request={stats['last_request_preview']}")
            if stats.get("last_response_preview"):
                lines.append(f"      last_response={stats['last_response_preview']}")
        lines.append("=" * 110)
        return "\n".join(lines)


# ============================================================================
# Module-level singleton (same pattern as before)
# ============================================================================

_llm_router_instance = None


def get_llm_router() -> LLMRouter:
    """Get or create the global LLM router instance."""
    global _llm_router_instance
    if _llm_router_instance is None:
        _llm_router_instance = LLMRouter()
    return _llm_router_instance


llm_router = get_llm_router()


# ============================================================================
# COMMENTED OUT: Previous LiteLLM Key Rotation Logic
# ============================================================================
#
# The following code was the original LiteLLM-based multi-key rotation
# system.  It is preserved here for reference but is no longer active.
#
# class LLMRouter:  # OLD VERSION
#     MAX_KEY_ROTATIONS = 5
#
#     def _load_env_keys(self):
#         self.gemini_credentials = [...]
#         self.groq_credentials = [...]
#         self._credentials_by_provider = {...}
#         self._provider_cursor = {...}
#
#     def _create_litellm_router(self) -> Router:
#         from litellm import Router as LiteLLMRouter
#         ...
#
#     def _create_instructor_client(self) -> instructor.Instructor:
#         return instructor.from_litellm(
#             completion=self._completion_with_logging,
#             mode=instructor.Mode.JSON,
#         )
#
#     def _ordered_credentials(self, model_hint):
#         ...
#
#     def _completion_with_logging(self, **kwargs):
#         ...  # Round-robin key rotation with per-key logging
#
