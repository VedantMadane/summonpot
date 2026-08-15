"""Tests for deterministic tool and capability construction."""

from __future__ import annotations

import asyncio
import inspect
import threading
from typing import Any

from summonpot.models import ToolDef
from summonpot.tools import build_tool_from_func, tool


def test_tool_decorator_uses_function_metadata_and_defaults():
    @tool()
    def transform(
        values: list[int], options: dict[str, bool] | None = None
    ) -> tuple[int, ...]:
        """Transform typed values."""
        return tuple(values) if options is None else tuple(reversed(values))

    assert transform.name == "transform"
    assert transform.description == "Transform typed values."
    assert [parameter.name for parameter in transform.parameters] == [
        "values",
        "options",
    ]
    assert transform.parameters[0].type_annotation == "list[int]"
    assert transform.parameters[0].required is True
    assert transform.parameters[1].type_annotation == "dict[str, bool] | None"
    assert transform.parameters[1].required is False
    assert transform.parameters[1].default is None


def test_build_tool_skips_method_receiver_from_schema():
    def combine(self: Any, value: int, enabled: bool = True) -> dict[str, Any]:
        """Combine exact inputs."""
        return {"value": value, "enabled": enabled}

    definition = build_tool_from_func(combine)

    assert [parameter.name for parameter in definition.parameters] == [
        "value",
        "enabled",
    ]


def test_tooldef_executes_sync_function():
    def combine(value: int, enabled: bool = True) -> dict[str, Any]:
        return {"value": value, "enabled": enabled}

    definition = build_tool_from_func(combine)

    assert asyncio.run(definition.call(value=3)) == {"value": 3, "enabled": True}


def test_tooldef_executes_async_function():
    async def fetch(identifier: str) -> str:
        """Fetch one record."""
        return f"record:{identifier}"

    definition = build_tool_from_func(fetch)

    assert asyncio.run(definition.call(identifier="123")) == "record:123"


def test_sync_capabilities_run_concurrently_off_the_event_loop():
    """A slow synchronous capability must not stall the other requests."""
    # The barrier only releases if all three calls are in flight at once; if they
    # are serialised onto the event loop the first wait() times out instead.
    barrier = threading.Barrier(3, timeout=10)

    def gated(value: str) -> str:
        barrier.wait()
        return value

    definition = build_tool_from_func(gated)

    async def run_all():
        return await asyncio.gather(*(definition.call(value=str(n)) for n in range(3)))

    assert asyncio.run(run_all()) == ["0", "1", "2"]


def test_tooldef_awaits_callable_objects_with_async_call():
    class Repository:
        async def __call__(self, key: str) -> str:
            return f"value:{key}"

    definition = ToolDef(name="repository", description="", fn=Repository())

    result = asyncio.run(definition.call(key="k"))

    assert result == "value:k"
    assert not inspect.isawaitable(result)


def test_unannotated_parameters_default_to_string_type():
    def lookup(value):
        return value

    definition = build_tool_from_func(lookup)

    assert definition.parameters[0].type_annotation == "str"
