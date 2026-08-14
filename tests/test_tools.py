"""Tests for deterministic tool and capability construction."""

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
from typing import Any

import pytest

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


def test_unbound_method_capability_is_rejected():
    """Nothing can supply the receiver, so this fails at registration, not at call."""
    with pytest.raises(TypeError, match="unbound method"):
        build_tool_from_func(CapabilityService.lookup)


def test_unbound_method_is_detected_whatever_the_receiver_is_called():
    """Detection reads the owning class, not the first parameter's spelling."""
    with pytest.raises(TypeError, match="'receiver'"):
        build_tool_from_func(CapabilityService.lookup_oddly_named)


def test_plain_function_with_a_self_field_is_accepted():
    """`self` is a legal business field name on a function that is not a method."""

    def render(self: str, template: str) -> str:
        """Render a template for a self-describing entity."""
        return self + template

    definition = build_tool_from_func(render)

    assert [parameter.name for parameter in definition.parameters] == [
        "self",
        "template",
    ]


def test_staticmethod_and_classmethod_capabilities_are_accepted():
    """Both are callable as reached, so neither is an unbound method."""
    static_definition = build_tool_from_func(CapabilityService.normalize)
    class_definition = build_tool_from_func(CapabilityService.describe)

    assert [p.name for p in static_definition.parameters] == ["value"]
    assert [p.name for p in class_definition.parameters] == ["value"]
    assert asyncio.run(static_definition.call(value="v")) == "v"
    assert asyncio.run(class_definition.call(value="v")) == "CapabilityService:v"


def test_bound_method_capability_is_accepted():
    class Service:
        def __init__(self, prefix: str) -> None:
            self.prefix = prefix

        def lookup(self, key: str) -> str:
            """Look up a key."""
            return f"{self.prefix}:{key}"

    definition = build_tool_from_func(Service("accounts").lookup)

    assert definition.name == "lookup"
    assert [parameter.name for parameter in definition.parameters] == ["key"]
    assert asyncio.run(definition.call(key="7")) == "accounts:7"


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


def test_partial_capability_uses_the_wrapped_function_name_and_docstring():
    def fetch_record(table: str, identifier: str) -> str:
        """Fetch one record from an approved table."""
        return f"{table}:{identifier}"

    definition = build_tool_from_func(functools.partial(fetch_record, "accounts"))

    assert definition.name == "fetch_record"
    assert definition.description == "Fetch one record from an approved table."
    # The bound argument must not be offered to the model again.
    assert [parameter.name for parameter in definition.parameters] == ["identifier"]
    assert asyncio.run(definition.call(identifier="7")) == "accounts:7"


def test_callable_object_capability_is_named_after_its_class():
    class LookupAccount:
        """Look up an account through a framework-owned connection."""

        def __init__(self, connection: str) -> None:
            self.connection = connection

        def __call__(self, identifier: str) -> str:
            return f"{self.connection}:{identifier}"

    definition = build_tool_from_func(LookupAccount("primary"))

    assert definition.name == "LookupAccount"
    assert definition.description == (
        "Look up an account through a framework-owned connection."
    )
    assert [parameter.name for parameter in definition.parameters] == ["identifier"]
    assert definition.parameters[0].type_annotation == "str"
    assert asyncio.run(definition.call(identifier="7")) == "primary:7"


def test_non_callable_capability_raises_a_clear_error():
    with pytest.raises(TypeError, match="Capability must be callable, got 'int'"):
        build_tool_from_func(42)  # pyright: ignore[reportArgumentType]


def test_unannotated_parameters_default_to_string_type():
    def lookup(value):
        return value

    definition = build_tool_from_func(lookup)

    assert definition.parameters[0].type_annotation == "str"


def test_async_callable_object_capability_is_awaited():
    """The async form must not hand an un-awaited coroutine back as the result."""

    class AsyncRepository:
        """Look up an account asynchronously."""

        def __init__(self, connection: str) -> None:
            self.connection = connection

        async def __call__(self, identifier: str) -> str:
            return f"{self.connection}:{identifier}"

    definition = build_tool_from_func(AsyncRepository("primary"))

    result = asyncio.run(definition.call(identifier="7"))

    assert definition.name == "AsyncRepository"
    assert result == "primary:7"
    assert not inspect.isawaitable(result)
class CapabilityService:
    """Capabilities reached through a class, used by the receiver tests."""

    def __init__(self, prefix: str = "svc") -> None:
        self.prefix = prefix

    def lookup(self, key: str) -> str:
        """Look up a key."""
        return f"{self.prefix}:{key}"

    def lookup_oddly_named(receiver, key: str) -> str:
        """Look up a key through a receiver that is not called self."""
        return key

    @staticmethod
    def normalize(value: str) -> str:
        """Normalize a value."""
        return value

    @classmethod
    def describe(cls, value: str) -> str:
        """Describe a value."""
        return f"{cls.__name__}:{value}"
