"""Tests for the HTTP server — verifies FastAPI routes are built from endpoints."""

from __future__ import annotations

import logging
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import (
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

from summonpot import Depends, Pot, __version__
from summonpot.server import build_app


class AnalysisRequest(BaseModel):
    text: str = Field(min_length=3)
    max_topics: int = Field(default=3, ge=1, le=10, alias="maxTopics")


class AnalysisResponse(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    topics: list[str]


def test_build_app_creates_route(mock_runtime):
    pot = mock_runtime(mock_response="Hello, world!")

    @pot.summon("/hello")
    def hello(name: str) -> str:
        """Greet someone."""
        return ""

    app = build_app(pot)
    client = TestClient(app)
    response = client.post("/hello", json={"name": "world"})
    assert response.status_code == 200
    assert response.json() == "Hello, world!"


def test_build_app_uses_pydantic_request_and_response_models(mock_runtime):
    pot = mock_runtime(
        mock_response={"sentiment": "positive", "topics": ["agents", "apis"]}
    )

    @pot.summon("/analyze")
    def analyze(request: AnalysisRequest) -> AnalysisResponse:
        """Analyze text."""
        raise NotImplementedError

    client = TestClient(build_app(pot))
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/analyze"]["post"]

    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert request_schema == {"$ref": "#/components/schemas/AnalysisRequest"}
    assert response_schema == {"$ref": "#/components/schemas/AnalysisResponse"}

    valid = client.post("/analyze", json={"text": "Great framework"})
    assert valid.status_code == 200
    assert valid.json() == {"sentiment": "positive", "topics": ["agents", "apis"]}
    pot._runtime.call.assert_awaited_once_with(
        pot.endpoints[0], {"text": "Great framework", "maxTopics": 3}
    )

    invalid = client.post("/analyze", json={"text": "x"})
    assert invalid.status_code == 422


def test_dependency_parameters_do_not_leak_into_http_contract(mock_runtime):
    def analyze_records(text: str) -> dict[str, str]:
        """Run exact deterministic analysis."""
        return {"text": text}

    pot = mock_runtime(
        mock_response={"sentiment": "positive", "topics": ["capabilities"]}
    )

    @pot.summon("/analyze")
    def analyze(
        request: AnalysisRequest,
        records=Depends(analyze_records),
    ) -> AnalysisResponse:
        """Analyze using only the declared operation."""
        raise AssertionError("declarative endpoint body must not execute")

    client = TestClient(build_app(pot))
    operation = client.get("/openapi.json").json()["paths"]["/analyze"]["post"]

    assert operation.get("parameters", []) == []
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AnalysisRequest"
    }
    response = client.post("/analyze", json={"text": "Exact operation"})
    assert response.status_code == 200
    assert response.json() == {
        "sentiment": "positive",
        "topics": ["capabilities"],
    }


def test_request_schema_preserves_unions_generics_and_any(mock_runtime):
    """The HTTP contract must match the signature, not a parsed display string."""
    pot = mock_runtime(mock_response="ok")

    @pot.summon("/typed")
    def typed(
        q: str,
        limit: int | None = None,
        payload: Any = None,
        items: list[int] | None = None,
    ) -> str:
        """Typed endpoint."""
        return ""

    client = TestClient(build_app(pot))
    properties = client.get("/openapi.json").json()["components"]["schemas"][
        "typedRequest"
    ]["properties"]

    # A nullable parameter stays nullable instead of collapsing to its first member.
    assert properties["limit"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]
    # Any imposes no constraint instead of silently becoming a string.
    assert "type" not in properties["payload"]

    assert client.post("/typed", json={"q": "x", "limit": None}).status_code == 200
    assert (
        client.post("/typed", json={"q": "x", "payload": {"a": 1}}).status_code == 200
    )
    assert client.post("/typed", json={"q": "x", "limit": 5}).status_code == 200


def test_request_schema_validates_generic_element_types(mock_runtime):
    """list[int] used to fail open, handing the agent the wrong types."""
    pot = mock_runtime(mock_response="ok")

    @pot.summon("/items")
    def items(values: list[int]) -> str:
        """Items endpoint."""
        return ""

    client = TestClient(build_app(pot))

    assert client.post("/items", json={"values": [1, 2]}).status_code == 200
    assert client.post("/items", json={"values": ["a", "b"]}).status_code == 422


@pytest.mark.parametrize(
    ("raised", "expected_status", "expected_detail"),
    [
        (
            UsageLimitExceeded("request limit of 2 exceeded"),
            429,
            "exceeded its configured usage limit",
        ),
        (TimeoutError(), 504, "timed out"),
        (
            ModelHTTPError(status_code=429, model_name="openai:gpt-4o-mini"),
            429,
            "status 429",
        ),
        (
            ModelHTTPError(status_code=500, model_name="openai:gpt-4o-mini"),
            502,
            "status 500",
        ),
        (
            UnexpectedModelBehavior("Exceeded maximum retries"),
            502,
            "did not satisfy the endpoint contract",
        ),
    ],
)
def test_runtime_failures_map_to_stable_http_responses(
    raised, expected_status, expected_detail
):
    """Every one of these used to reach the caller as an opaque 500."""
    pot = Pot("svc")

    @pot.summon("/research")
    def research(query: str) -> str:
        """Research a topic."""
        return ""

    class FailingRuntime:
        async def call(self, endpoint, params):
            raise raised

    pot._runtime = FailingRuntime()
    client = TestClient(build_app(pot), raise_server_exceptions=False)

    response = client.post("/research", json={"query": "agents"})

    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"]


def test_unexpected_capability_failure_still_surfaces_as_a_server_error():
    """An error inside user code is a genuine 500, not a mislabelled gateway error."""
    pot = Pot("svc")

    @pot.summon("/research")
    def research(query: str) -> str:
        """Research a topic."""
        return ""

    class FailingRuntime:
        async def call(self, endpoint, params):
            raise ValueError("the accounts database is down")

    pot._runtime = FailingRuntime()
    client = TestClient(build_app(pot), raise_server_exceptions=False)

    assert client.post("/research", json={"query": "agents"}).status_code == 500


def test_build_app_requires_body_fields(mock_runtime):
    pot = mock_runtime()

    @pot.summon("/strict")
    def strict(required_field: int) -> str:
        """Strict endpoint."""
        return ""

    app = build_app(pot)
    client = TestClient(app)
    # Missing required field → 422 validation error
    response = client.post("/strict", json={})
    assert response.status_code == 422


def test_build_app_openapi_has_endpoints():
    pot = Pot("svc")

    @pot.summon("/analyze")
    def analyze(text: str) -> dict:
        """Analyze text."""
        return {}

    app = build_app(pot)
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    operation = paths["/analyze"]["post"]
    assert schema["info"]["version"] == __version__
    assert operation.get("parameters", []) == []
    assert operation["requestBody"]["required"] is True
    assert "/analyze" in paths
    assert "post" in paths["/analyze"]


def test_build_app_no_body_route_hides_internal_context(mock_runtime):
    pot = mock_runtime(mock_response="ready")

    @pot.summon("/health")
    def health() -> str:
        """Report readiness."""
        return ""

    client = TestClient(build_app(pot))
    operation = client.get("/openapi.json").json()["paths"]["/health"]["post"]

    assert operation.get("parameters", []) == []
    assert "requestBody" not in operation
    response = client.post("/health")
    assert response.status_code == 200
    assert response.json() == "ready"


@pytest.mark.parametrize(
    "raised",
    [
        UnexpectedModelBehavior("invalid model output: PRIVATE_CUSTOMER_RECORD_123"),
        UsageLimitExceeded("limit hit: PRIVATE_CUSTOMER_RECORD_123"),
    ],
)
def test_runtime_exception_text_is_not_returned_to_the_caller(raised, caplog):
    """Agent-loop exceptions can carry rejected model output or tool-call context."""
    pot = Pot("svc")

    @pot.summon("/research")
    def research(query: str) -> str:
        """Research a topic."""
        return ""

    class FailingRuntime:
        async def call(self, endpoint, params):
            raise raised

    pot._runtime = FailingRuntime()
    client = TestClient(build_app(pot), raise_server_exceptions=False)

    with caplog.at_level(logging.WARNING, logger="summonpot.server"):
        response = client.post("/research", json={"query": "agents"})

    assert "PRIVATE_CUSTOMER_RECORD_123" not in response.text
    # The operator still gets the detail.
    assert "PRIVATE_CUSTOMER_RECORD_123" in caplog.text
