"""Safe native query values stay useful across the HTTP carrier."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from summonpot import Summon
from summonpot.runtime import Runtime
from summonpot.server import build_app


class Result(BaseModel):
    value: str


@pytest.mark.parametrize(
    "annotation,raw,expected",
    [
        (date, "2026-09-08", date(2026, 9, 8)),
        (time, "12:30:00", time(12, 30)),
        (time, "12:30:00+03:00", time.fromisoformat("12:30:00+03:00")),
        (timedelta, "PT90S", timedelta(seconds=90)),
        (Decimal, "123.45", Decimal("123.45")),
        (bytes, "hello", b"hello"),
        (
            UUID,
            "12345678-1234-5678-1234-567812345678",
            UUID("12345678-1234-5678-1234-567812345678"),
        ),
        (datetime, "2026-09-08T12:30:00", datetime(2026, 9, 8, 12, 30)),
        (
            datetime,
            "2026-09-08T12:30:00+03:00",
            datetime.fromisoformat("2026-09-08T12:30:00+03:00"),
        ),
    ],
)
def test_native_query_values_reach_agent_and_custom_runtime(
    annotation: Any, raw, expected, monkeypatch
):
    prompts = []
    typed_values = []

    def model(messages, info):
        prompts.extend(
            part.content
            for message in messages
            for part in message.parts
            if isinstance(part, UserPromptPart)
        )
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"value": "seen"})]
        )

    summon = Summon("native-query")
    summon._runtime = Runtime(model=FunctionModel(model))

    @summon("/value", method="GET")
    def endpoint(value: annotation) -> Result:  # type: ignore[valid-type]  # pyright: ignore[reportInvalidTypeForm]
        """Use the supplied identifier or timestamp."""
        ...

    original = summon._runtime.call

    async def inspect_compatibility(endpoint, params):
        typed_values.append(params.typed["value"])
        return await original(endpoint, params)

    monkeypatch.setattr(summon._runtime, "call", inspect_compatibility)
    response = TestClient(build_app(summon)).get("/value", params={"value": raw})
    assert response.status_code == 200, response.text
    assert typed_values == [expected]
    assert type(typed_values[0]) is annotation
    assert any(str(expected) in prompt for prompt in prompts)


def test_native_uuid_projection_cannot_mutate_canonical_or_prompt_values():
    from summonpot._execution import (
        _prepare_request,
        _registered_plan,
        _validated_transport_request,
    )

    summon = Summon("native-isolation")

    @summon("/value", method="GET")
    def endpoint(value: UUID) -> Result:
        """Use the identifier."""
        ...

    plan = _registered_plan(summon.endpoints[0])
    assert plan is not None
    original = UUID("12345678-1234-5678-1234-567812345678")
    values = {"value": [original, {"again": original}]}
    carrier = _validated_transport_request(plan, values, typed=values)
    public_uuid = carrier.typed["value"][0]
    assert type(public_uuid) is UUID
    assert public_uuid is not original
    object.__setattr__(public_uuid, "int", 0)
    assert carrier.typed["value"][1]["again"] == original
    carrier["value"][0] = "changed"
    prepared = _prepare_request(plan, carrier)
    assert prepared.typed["value"][0] is original
    assert original.int != 0
    assert prepared["value"][0] == str(original)


def test_native_projection_does_not_call_custom_timezone_or_subclass_hooks():
    from datetime import tzinfo

    from summonpot._execution import _inert_transport_value

    calls = []

    class Zone(tzinfo):
        def utcoffset(self, dt):
            calls.append("offset")
            raise RuntimeError("application timezone")

    class Identifier(UUID):
        def __str__(self):
            calls.append("uuid")
            raise RuntimeError("application UUID")

    class Timestamp(datetime):
        def __str__(self):
            calls.append("datetime")
            raise RuntimeError("application datetime")

    values = [
        datetime(2026, 9, 8, tzinfo=Zone()),
        Identifier(int=3),
        Timestamp(2026, 9, 8),
    ]
    for value in values:
        assert _inert_transport_value(value) == "<unavailable>"
        assert _inert_transport_value(value, native=True) == "<unavailable>"
    assert calls == []
