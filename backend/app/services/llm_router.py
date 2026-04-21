"""
LLM Router: Explicit per-key request logging with round-robin provider selection.
Structured outputs still go through Instructor, but the underlying completion call
is wrapped so we can record which env key was used, what was requested, what came
back, and cumulative request counts.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from copy import deepcopy
from typing import Any, Callable, Tuple, TYPE_CHECKING

import instructor

if TYPE_CHECKING:
    from litellm import Router  # type: ignore[import-not-found]
else:
    Router = Any

logger = logging.getLogger(__name__)


class LLMRouter:
    """Route LLM requests through explicit API keys with auditable logging."""

    def __init__(self):
        self.provider = "litellm-router"
        self._lock = threading.Lock()
        self._request_sequence = 0
        self._load_env_keys()
        self.router = self._create_litellm_router()
        self.client = self._create_instructor_client()
        logger.info("LLM Router initialized with explicit per-key logging.")

    def _load_env_keys(self):
        """Load the exact env var names so logs can identify each credential."""
        self.gemini_credentials = [
            {
                "env_name": f"GEMINI_API_KEY{i}",
                "api_key": os.getenv(f"GEMINI_API_KEY{i}"),
                "provider": "gemini",
                "model": "gemini/gemini-2.5-flash",
            }
            for i in range(1, 6)
            if os.getenv(f"GEMINI_API_KEY{i}")
        ]
        self.groq_credentials = [
            {
                "env_name": f"GROQ_API_KEY{i}",
                "api_key": os.getenv(f"GROQ_API_KEY{i}"),
                "provider": "groq",
                "model": "groq/llama-3.3-70b-versatile",
            }
            for i in range(1, 6)
            if os.getenv(f"GROQ_API_KEY{i}")
        ]

        self._credentials_by_provider = {
            "gemini": self.gemini_credentials,
            "groq": self.groq_credentials,
        }
        self._provider_cursor = {"gemini": 0, "groq": 0}
        self._stats = {
            "total_attempts": 0,
            "total_successes": 0,
            "total_failures": 0,
            "by_key": {},
            "events": [],
        }

        for credential in self.gemini_credentials + self.groq_credentials:
            self._stats["by_key"][credential["env_name"]] = {
                "provider": credential["provider"],
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "last_error": None,
                "last_request_preview": None,
                "last_response_preview": None,
            }

        if not self.gemini_credentials and not self.groq_credentials:
            logger.warning("No Groq or Gemini API keys found. Extraction will fail.")
        else:
            logger.info(
                "Loaded LLM credentials | gemini=%d | groq=%d",
                len(self.gemini_credentials),
                len(self.groq_credentials),
            )

    def _create_litellm_router(self) -> Router:
        """Create a minimal router for compatibility with existing call sites."""
        from litellm import Router as LiteLLMRouter  # type: ignore[import-not-found]

        model_list = []
        for credential in self.gemini_credentials:
            model_list.append(
                {
                    "model_name": credential["provider"],
                    "litellm_params": {
                        "model": credential["model"],
                        "api_key": credential["api_key"],
                        "temperature": 0.0,
                    },
                }
            )
        for credential in self.groq_credentials:
            model_list.append(
                {
                    "model_name": credential["provider"],
                    "litellm_params": {
                        "model": credential["model"],
                        "api_key": credential["api_key"],
                        "temperature": 0.0,
                    },
                }
            )

        return LiteLLMRouter(
            model_list=model_list,
            num_retries=0,
            fallbacks=[],
            set_verbose=False,
        )

    def _create_instructor_client(self) -> instructor.Instructor:
        """Wrap the logging completion function with Instructor to enforce Pydantic schemas."""
        return instructor.from_litellm(
            completion=self._completion_with_logging,
            mode=instructor.Mode.JSON,
        )

    def _serialize_request_preview(self, kwargs: dict[str, Any]) -> str:
        messages = kwargs.get("messages", []) or []
        preview_items = []
        for message in messages:
            if not isinstance(message, dict):
                preview_items.append(str(message)[:500])
                continue
            preview_items.append(
                {
                    "role": message.get("role"),
                    "chars": len(str(message.get("content", ""))),
                    "preview": str(message.get("content", ""))[:500],
                }
            )
        summary = {
            "model_hint": kwargs.get("model"),
            "temperature": kwargs.get("temperature"),
            "max_tokens": kwargs.get("max_tokens") or kwargs.get("max_completion_tokens"),
            "timeout": kwargs.get("timeout"),
            "response_format": getattr(kwargs.get("response_format"), "__name__", str(kwargs.get("response_format"))),
            "messages": preview_items,
        }
        return json.dumps(summary, ensure_ascii=True, default=str)

    def _serialize_response_preview(self, response: Any) -> str:
        try:
            usage = getattr(response, "usage", None)
            usage_data = usage.model_dump() if hasattr(usage, "model_dump") else (usage or None)
            choices = getattr(response, "choices", []) or []
            content = None
            if choices:
                message = getattr(choices[0], "message", None)
                if message is not None:
                    content = getattr(message, "content", None)
            payload = {
                "model": getattr(response, "model", None),
                "usage": usage_data,
                "content_preview": (content[:1200] if isinstance(content, str) else str(content)[:1200]),
            }
            return json.dumps(payload, ensure_ascii=True, default=str)
        except Exception:
            return str(response)[:1200]

    def _ordered_credentials(self, model_hint: str | None) -> list[dict[str, Any]]:
        preferred_provider = "groq" if model_hint and "fallback" in model_hint.lower() else "gemini"
        secondary_provider = "gemini" if preferred_provider == "groq" else "groq"
        ordered: list[dict[str, Any]] = []

        for provider in (preferred_provider, secondary_provider):
            credentials = self._credentials_by_provider.get(provider, [])
            if not credentials:
                continue
            cursor = self._provider_cursor[provider] % len(credentials)
            rotated = credentials[cursor:] + credentials[:cursor]
            ordered.extend(rotated)
        return ordered

    def _log_event(self, record: dict[str, Any]) -> None:
        self._stats["events"].append(record)
        if len(self._stats["events"]) > 100:
            self._stats["events"] = self._stats["events"][-100:]

    def _completion_with_logging(self, **kwargs: Any) -> Any:
        request_id = None
        request_preview = self._serialize_request_preview(kwargs)
        model_hint = kwargs.get("model")
        ordered_credentials = self._ordered_credentials(model_hint)

        if not ordered_credentials:
            raise RuntimeError("No LLM credentials available for completion")

        last_error: Exception | None = None
        for credential in ordered_credentials:
            with self._lock:
                self._request_sequence += 1
                request_id = self._request_sequence
                self._stats["total_attempts"] += 1
                self._stats["by_key"][credential["env_name"]]["attempts"] += 1
                self._stats["by_key"][credential["env_name"]]["last_request_preview"] = request_preview

            request_started_at = time.time()
            logger.info(
                "[LLM-REQUEST #%d] key=%s provider=%s model=%s request=%s",
                request_id,
                credential["env_name"],
                credential["provider"],
                credential["model"],
                request_preview,
            )

            call_kwargs = dict(kwargs)
            call_kwargs["model"] = credential["model"]
            call_kwargs["api_key"] = credential["api_key"]
            call_kwargs.pop("model_list", None)

            try:
                from litellm import completion as litellm_completion  # type: ignore[import-not-found]

                response = litellm_completion(**call_kwargs)
                response_preview = self._serialize_response_preview(response)
                duration = time.time() - request_started_at

                with self._lock:
                    self._stats["total_successes"] += 1
                    self._stats["by_key"][credential["env_name"]]["successes"] += 1
                    self._stats["by_key"][credential["env_name"]]["last_response_preview"] = response_preview
                    self._provider_cursor[credential["provider"]] = (
                        self._provider_cursor[credential["provider"]] + 1
                    ) % max(len(self._credentials_by_provider[credential["provider"]]), 1)
                    self._log_event(
                        {
                            "request_id": request_id,
                            "env_name": credential["env_name"],
                            "provider": credential["provider"],
                            "model": credential["model"],
                            "status": "success",
                            "duration_sec": round(duration, 3),
                            "response_preview": response_preview,
                        }
                    )

                logger.info(
                    "[LLM-RESPONSE #%d] key=%s provider=%s duration=%.2fs response=%s",
                    request_id,
                    credential["env_name"],
                    credential["provider"],
                    duration,
                    response_preview,
                )
                return response

            except Exception as exc:
                last_error = exc
                duration = time.time() - request_started_at
                error_text = f"{type(exc).__name__}: {exc}"

                with self._lock:
                    self._stats["total_failures"] += 1
                    self._stats["by_key"][credential["env_name"]]["failures"] += 1
                    self._stats["by_key"][credential["env_name"]]["last_error"] = error_text
                    self._log_event(
                        {
                            "request_id": request_id,
                            "env_name": credential["env_name"],
                            "provider": credential["provider"],
                            "model": credential["model"],
                            "status": "error",
                            "duration_sec": round(duration, 3),
                            "error": error_text,
                        }
                    )

                logger.warning(
                    "[LLM-ERROR #%d] key=%s provider=%s duration=%.2fs error=%s",
                    request_id,
                    credential["env_name"],
                    credential["provider"],
                    duration,
                    error_text,
                )

        if last_error is not None:
            raise last_error
        raise RuntimeError("LLM completion failed without raising an error")

    def get_structured_client(self) -> Tuple[instructor.Instructor, str]:
        """Return the instructor-wrapped client and the virtual model name."""
        return self.client, "talash-primary"

    def get_raw_client(self) -> Tuple[Router, str]:
        """Return the raw router for standard chat completions without Pydantic."""
        return self.router, "talash-primary"

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


_llm_router_instance = None


def get_llm_router() -> LLMRouter:
    """Get or create the global LLM router instance."""
    global _llm_router_instance
    if _llm_router_instance is None:
        _llm_router_instance = LLMRouter()
    return _llm_router_instance


llm_router = get_llm_router()
