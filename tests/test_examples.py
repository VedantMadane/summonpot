"""Acceptance coverage for the executable example progression."""

import runpy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from summonpot import AgentChoice, Exactly, FromRequest, FromResult
from summonpot.runtime import Runtime
from summonpot.server import build_app

ROOT = Path(__file__).resolve().parent.parent


EXAMPLES = [
    ("basic_app.py", "/review", "post"),
    ("02_required_capability.py", "/quotes", "post"),
    ("03_agentic_order.py", "/orders", "post"),
    ("04_http_methods.py", "/products", "get"),
    ("04_http_methods.py", "/products", "post"),
    ("05_bounded_runtime.py", "/summaries", "post"),
    ("06_support_service/app.py", "/support", "post"),
    ("07_bound_operation.py", "/customers/view", "post"),
]


def _load_example(relative_path: str, monkeypatch):
    example = ROOT / "examples" / relative_path
    monkeypatch.syspath_prepend(str(example.parent))
    return runpy.run_path(str(example), run_name=f"example_{relative_path}")["summon"]


@pytest.mark.parametrize(("relative_path", "route", "method"), EXAMPLES)
def test_every_example_builds_its_advertised_openapi_route(
    relative_path, route, method, monkeypatch
):
    summon = _load_example(relative_path, monkeypatch)

    schema = build_app(summon).openapi()

    assert method in schema["paths"][route]


def test_minimal_example_serves_a_real_keyless_request(monkeypatch):
    monkeypatch.setenv("SUMMONPOT_MODEL", "test")
    summon = _load_example("basic_app.py", monkeypatch)

    response = TestClient(build_app(summon)).post(
        "/review", json={"text": "The contract is concise and clear."}
    )

    assert response.status_code == 200
    assert set(response.json()) == {"sentiment", "summary"}


def test_bound_operation_example_runs_through_real_http(monkeypatch):
    summon = _load_example("07_bound_operation.py", monkeypatch)
    turns = 0

    def model_function(messages, info: AgentInfo):
        nonlocal turns
        turns += 1
        if turns == 1:
            tool = info.function_tools[0]
            assert tool.name == "load_customer"
            assert sorted(tool.parameters_json_schema["properties"]) == ["format"]
            return ModelResponse(
                parts=[ToolCallPart("load_customer", {"format": "summary"})]
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {
                        "customer_id": "customer-7",
                        "display": "Ada — active",
                    },
                )
            ]
        )

    summon._runtime = Runtime(model=FunctionModel(model_function))
    response = TestClient(build_app(summon)).post(
        "/customers/view", json={"customer_id": "customer-7"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "customer_id": "customer-7",
        "display": "Ada — active",
    }


def test_support_example_declares_the_typed_operation_chain(monkeypatch):
    summon = _load_example("06_support_service/app.py", monkeypatch)
    tools = {tool.name: tool for tool in summon.endpoints[0].tools}

    customer = tools["load_customer"]
    policy = tools["load_policy"]
    ticket = tools["create_ticket"]

    assert customer.contract.bind == {"customer_id": FromRequest("customer_id")}
    assert policy.contract.bind == {"topic": AgentChoice()}
    assert ticket.contract.bind == {
        "customer_id": FromResult(customer.contract, "customer_id"),
        "priority": AgentChoice(),
        "summary": AgentChoice(),
    }
    assert ticket.contract.after == (customer.contract, policy.contract)
    assert ticket.bounds == Exactly(1)
    assert customer.required is True
    assert policy.required is True
    assert ticket.required is True


def test_support_example_guide_states_the_current_binding_boundary():
    guide = (ROOT / "examples/README.md").read_text()

    assert "FromRequest" in guide
    assert "FromResult" in guide
    assert "AgentChoice" in guide
    assert "does not inject bound values" in guide
    assert "filtered model schema" in guide
    assert "one permitted start" in guide


def test_readme_documents_the_pot_to_summon_migration():
    readme = (ROOT / "README.md").read_text()

    assert "Migrating from the 0.5 API" in readme
    assert "from summonpot import Pot" in readme
    assert "from summonpot import Summon" in readme
    assert "`pot` → `summon`" in readme
    assert "`summonpot.pot` module have been removed" in readme
    assert "module-level variable named `summon`" in readme


def test_examples_use_one_documented_provider_installation():
    guide = (ROOT / "examples/README.md").read_text()
    bounded = (ROOT / "examples/05_bounded_runtime.py").read_text()

    assert "summonpot[serve,cli,openrouter]" in guide
    assert 'model="openrouter:openai/gpt-4o-mini"' in bounded
    assert "OPENAI_API_KEY" not in guide
