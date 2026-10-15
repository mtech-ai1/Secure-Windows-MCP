"""Thread-dispatch behaviour of ``tool_dispatch``.

Synchronous tool bodies normally use ``asyncio.to_thread`` so they cannot block
the MCP event loop.  UIAutomation/comtypes work additionally needs stable COM
apartment affinity, so ``run_sync_in_thread=False`` uses one dedicated UIA
worker instead of running inline on the event loop.

These tests do not require a live desktop.  They pin the dispatch semantics,
including the regression that a long WaitFor-style synchronous body must not
stall unrelated async work.
"""

import asyncio
import inspect
import threading
import time

import pytest

from windows_mcp.infrastructure import uia_thread_id, tool_dispatch


class TestThreadDispatch:
    async def test_default_sync_body_runs_off_event_loop_thread(self):
        @tool_dispatch()
        def my_tool():
            return threading.get_ident()

        caller = threading.get_ident()
        assert await my_tool() != caller

    async def test_affine_sync_body_runs_on_dedicated_worker(self):
        @tool_dispatch(run_sync_in_thread=False)
        def my_tool():
            return threading.get_ident()

        caller = threading.get_ident()
        owner = await my_tool()
        assert owner == uia_thread_id()
        assert owner != caller

    async def test_affine_sync_body_reuses_same_worker(self):
        @tool_dispatch(run_sync_in_thread=False)
        def my_tool():
            return threading.get_ident()

        assert await my_tool() == await my_tool() == uia_thread_id()

    async def test_async_body_is_awaited_on_the_calling_thread(self):
        @tool_dispatch()
        async def my_tool():
            await asyncio.sleep(0)
            return threading.get_ident()

        caller = threading.get_ident()
        assert await my_tool() == caller

    async def test_affinity_flag_does_not_move_async_body(self):
        """Async tools must explicitly hop only their UIA operation."""

        @tool_dispatch(run_sync_in_thread=False)
        async def my_tool():
            return threading.get_ident()

        caller = threading.get_ident()
        assert await my_tool() == caller


class TestBehaviourPreserved:
    async def test_return_value_preserved_for_affine_sync_body(self):
        @tool_dispatch(run_sync_in_thread=False)
        def my_tool():
            return {"key": "value", "count": 42}

        assert await my_tool() == {"key": "value", "count": 42}

    async def test_exception_propagates_for_affine_sync_body(self):
        @tool_dispatch(run_sync_in_thread=False)
        def my_tool():
            raise ValueError("something broke")

        with pytest.raises(ValueError, match="something broke"):
            await my_tool()

    def test_default_keeps_generic_worker_dispatch(self):
        parameter = inspect.signature(tool_dispatch).parameters["run_sync_in_thread"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is True


class TestEventLoopResponsiveness:
    async def test_long_affine_sync_body_does_not_stall_event_loop(self):
        """A WaitFor-style blocking body must not freeze unrelated async work."""

        @tool_dispatch(run_sync_in_thread=False)
        def blocking_tool():
            time.sleep(0.15)
            return "done"

        tool_task = asyncio.create_task(blocking_tool())

        async def ticker():
            await asyncio.sleep(0.02)
            return "tick"

        assert await ticker() == "tick"
        assert not tool_task.done()
        assert await tool_task == "done"
