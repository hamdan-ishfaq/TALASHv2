"""
Run asyncio coroutines from synchronous code (e.g. Celery workers).

Uses a dedicated event loop per call to avoid relying on asyncio.run() quirks
when the worker thread has a lingering loop policy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


def run_coro_sync(coro: Coroutine[Any, Any, T]) -> T:
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        asyncio.set_event_loop(None)
        loop.close()
