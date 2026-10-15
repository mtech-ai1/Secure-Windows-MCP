from typing import TypeVar, Callable, Awaitable
from windows_mcp.infrastructure.thread_affinity import run_uia_affine
from functools import wraps
import inspect
import asyncio

T = TypeVar("T")


def tool_dispatch(*, run_sync_in_thread: bool = True):
    """
    Decorator that runs a tool function off the MCP event loop.

    Args:
        run_sync_in_thread: For a synchronous ``func``, dispatch the call to a generic
            worker thread so it cannot block the event loop (the default). Set to False
            for UIAutomation/comtypes-affine tools: they run on the single dedicated UIA
            worker instead, preserving COM apartment affinity without blocking the MCP
            event loop. Ignored for async ``func``; async tools that need UIA must call
            ``run_uia_affine`` around the UIA operation itself.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            if run_sync_in_thread:
                # Generic synchronous work stays off the MCP event loop.
                return await asyncio.to_thread(func, *args, **kwargs)
            # UIA-affine synchronous work is serialized on one dedicated
            # apartment thread, so WaitFor and slow providers cannot freeze
            # cancellation, pings, or unrelated MCP tool calls.
            return await run_uia_affine(func, *args, **kwargs)

        return wrapper

    return decorator
