"""Tests for the Pot class — endpoint registration and introspection."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from summonpot import Depends, Pot, Required
from summonpot.tools import tool


class ResearchRequest(BaseModel):
    query: str
    depth: int = 1


class ResearchResponse(BaseModel):
    summary: str
    sources: list[str]


def test_pot_init():
    pot = Pot("svc")
    assert pot.name == "svc"
    assert pot.endpoints == []


def test_summon_registers_endpoint():
    pot = Pot("svc")

    @pot.summon("/research")
    def research_topic(query: str, depth: str = "standard") -> str:
        """Research this topic."""
        return ""

    assert len(pot.endpoints) == 1
    ep = pot.endpoints[0]
    assert ep.path == "/research"
    assert ep.name == "research_topic"
    assert ep.description == "Research this topic."
    assert ep.return_type == "str"
    assert [p.name for p in ep.parameters] == ["query", "depth"]
    assert ep.parameters[0].required is True
    assert ep.parameters[1].required is False
    assert ep.parameters[1].default == "standard"


def test_summon_registers_pydantic_input_and_output_contracts():
    pot = Pot("svc")

    @pot.summon("/research")
    def research(request: ResearchRequest) -> ResearchResponse:
        """Research a topic."""
        raise NotImplementedError

    endpoint = pot.endpoints[0]
    assert endpoint.input_model is ResearchRequest
    assert endpoint.output_model is ResearchResponse
    assert endpoint.return_type == "ResearchResponse"


def _register_with_unresolvable_annotations(source: str):
    """Register an endpoint whose annotations cannot be evaluated at runtime."""
    namespace: dict = {}
    # exec keeps the caller's `from __future__ import annotations`, which is what
    # leaves these annotations unevaluated at registration time.
    exec(source, namespace)


def test_summon_rejects_an_unresolvable_parameter_annotation():
    """Silently dropping the contract is what this must never do again."""
    with pytest.raises(TypeError, match="Could not resolve the annotation"):
        _register_with_unresolvable_annotations(
            "from summonpot import Pot\n"
            "pot = Pot('svc')\n"
            "@pot.summon('/research')\n"
            "def research(request: OnlyUnderTypeChecking) -> str:\n"
            "    '''Research a topic.'''\n"
            "    raise NotImplementedError\n"
        )


def test_summon_rejects_an_unresolvable_return_annotation():
    with pytest.raises(TypeError, match="the return type"):
        _register_with_unresolvable_annotations(
            "from summonpot import Pot\n"
            "pot = Pot('svc')\n"
            "@pot.summon('/research')\n"
            "def research(query: str) -> MissingResponseModel:\n"
            "    '''Research a topic.'''\n"
            "    raise NotImplementedError\n"
        )


def test_summon_rejects_a_model_defined_in_a_local_scope():
    """A model built inside a factory is the realistic way to hit this."""

    def build_pot():
        class LocalRequest(BaseModel):
            query: str

        pot = Pot("svc")

        @pot.summon("/research")
        def research(request: LocalRequest) -> str:
            """Research a topic."""
            raise NotImplementedError

        return pot

    with pytest.raises(TypeError, match="Could not resolve the annotation"):
        build_pot()


def test_summon_requires_a_docstring_goal():
    """The docstring is the agent's instructions, so an empty one is not usable."""
    pot = Pot("svc")

    with pytest.raises(TypeError, match="has no docstring"):

        @pot.summon("/research")
        def research(request: ResearchRequest) -> ResearchResponse:
            raise NotImplementedError


def test_summon_rejects_a_whitespace_only_docstring():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="has no docstring"):

        @pot.summon("/research")
        def research(request: ResearchRequest) -> ResearchResponse:
            """ """
            raise NotImplementedError


def test_summon_rejects_mixed_pydantic_and_scalar_inputs():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="exactly one request parameter"):

        @pot.summon("/research")
        def research(request: ResearchRequest, trace_id: str) -> ResearchResponse:
            """Research a topic."""
            raise NotImplementedError


def test_summon_compiles_dependency_parameters_as_closed_capabilities():
    def load_sources(query: str) -> list[str]:
        """Load sources for the validated query."""
        return [query]

    def rank_sources(sources: list[str]) -> list[str]:
        """Rank the loaded sources."""
        return sources

    pot = Pot("svc")

    @pot.summon("/research")
    def research(
        request: ResearchRequest,
        sources=Depends(load_sources),
        ranking=Required(rank_sources),
    ) -> ResearchResponse:
        """Research a topic using only the declared capabilities."""
        raise NotImplementedError

    endpoint = pot.endpoints[0]
    assert endpoint.input_model is ResearchRequest
    assert [parameter.name for parameter in endpoint.parameters] == ["request"]
    assert [tool.name for tool in endpoint.tools] == ["load_sources", "rank_sources"]
    assert [tool.required for tool in endpoint.tools] == [False, True]


def test_summon_rejects_duplicate_capability_names():
    def lookup(query: str) -> str:
        return query

    def second_lookup(query: str) -> str:
        return query

    second_lookup.__name__ = "lookup"
    pot = Pot("svc")

    with pytest.raises(TypeError, match="Duplicate capability name: lookup"):

        @pot.summon("/research")
        def research(
            request: ResearchRequest,
            first=Depends(lookup),
            second=Depends(second_lookup),
        ) -> ResearchResponse:
            """Research a topic."""
            raise NotImplementedError


def test_pot_level_tools_shared_across_endpoints():
    pot = Pot("svc", tools=[search_web_raw])

    @pot.summon("/one")
    def one(q: str) -> str:
        """One."""
        return ""

    @pot.summon("/two")
    def two(q: str) -> str:
        """Two."""
        return ""

    assert len(pot.endpoints[0].tools) == 1
    assert len(pot.endpoints[1].tools) == 1
    assert pot.endpoints[0].tools[0].name == "search_web_raw"


def test_endpoint_specific_tools_merged():
    pot = Pot("svc", tools=[search_web_raw])

    @pot.summon("/custom", tools=[translate_raw])
    def custom(q: str) -> str:
        """Custom."""
        return ""

    names = [t.name for t in pot.endpoints[0].tools]
    assert names == ["search_web_raw", "translate_raw"]


def test_tool_decorator_builds_tooldef():
    @tool(name="my_tool", description="Does a thing")
    def some_func(x: int) -> int:
        """Ignored — description override wins."""
        return x

    assert some_func.name == "my_tool"
    assert some_func.description == "Does a thing"
    assert some_func.parameters[0].name == "x"
    assert some_func.parameters[0].type_annotation == "int"


def test_repr():
    pot = Pot("svc")

    @pot.summon("/x")
    def x() -> str:
        """X."""
        return ""

    assert "endpoints=1" in repr(pot)


# --- helpers (plain functions, not decorated) ---


def search_web_raw(query: str) -> list[dict]:
    """Search the web for information."""
    return []


def translate_raw(text: str, target: str = "es") -> str:
    """Translate text to a target language."""
    return text


def test_summon_accepts_explicitly_quoted_forward_references():
    """`request: "ResearchRequest"` is a valid annotation and must not be rejected.

    Under PEP 563 the stored source is `'"ResearchRequest"'`, so evaluating it once
    yields the string `'ResearchRequest'` rather than the class.
    """
    pot = Pot("svc")

    @pot.summon("/research")
    def research(request: "ResearchRequest") -> "ResearchResponse":  # noqa: UP037
        """Research a topic."""
        raise NotImplementedError

    endpoint = pot.endpoints[0]
    assert endpoint.input_model is ResearchRequest
    assert endpoint.output_model is ResearchResponse


def test_summon_still_rejects_a_quoted_name_that_does_not_exist():
    with pytest.raises(TypeError, match="'StillMissing'"):
        _register_with_unresolvable_annotations(
            "from summonpot import Pot\n"
            "pot = Pot('svc')\n"
            "@pot.summon('/research')\n"
            'def research(request: "StillMissing") -> str:\n'
            "    '''Research a topic.'''\n"
            "    raise NotImplementedError\n"
        )


def test_summon_resolves_forward_references_inside_container_annotations():
    """`list["ResearchResponse"]` must resolve, not stay a container of strings."""
    pot = Pot("svc")

    @pot.summon("/research")
    def research(request: "ResearchRequest") -> "ResearchResponse":  # noqa: UP037
        """Research a topic."""
        raise NotImplementedError

    @pot.summon("/batch")
    def batch(items: list["ResearchRequest"]) -> dict[str, "ResearchResponse"]:  # noqa: UP037
        """Research several topics."""
        raise NotImplementedError

    assert pot.endpoints[0].input_model is ResearchRequest
    # The container resolved to real classes, so it renders with their names rather
    # than as a container of quoted strings.
    batch_endpoint = pot.endpoints[1]
    assert batch_endpoint.parameters[0].type_annotation == "list[ResearchRequest]"
    assert batch_endpoint.return_type == "dict[str, ResearchResponse]"


def test_summon_rejects_a_missing_name_nested_in_a_container():
    with pytest.raises(TypeError, match="'MissingInside'"):
        _register_with_unresolvable_annotations(
            "from summonpot import Pot\n"
            "pot = Pot('svc')\n"
            "@pot.summon('/research')\n"
            'def research(items: list["MissingInside"]) -> str:\n'
            "    '''Research topics.'''\n"
            "    raise NotImplementedError\n"
        )


def test_summon_rejects_a_path_without_a_leading_slash():
    """Such a path registers and builds, but no request can ever reach it."""
    pot = Pot("svc")

    with pytest.raises(ValueError, match="must start with '/'"):

        @pot.summon("research")
        def research(request: ResearchRequest) -> ResearchResponse:
            """Research a topic."""
            raise NotImplementedError


def test_summon_rejects_a_duplicate_path():
    """Starlette dispatches the first match, so the second was silently dead."""
    pot = Pot("svc")

    @pot.summon("/research")
    def research(request: ResearchRequest) -> ResearchResponse:
        """Research a topic."""
        raise NotImplementedError

    with pytest.raises(ValueError, match="POST /research is already registered"):

        @pot.summon("/research")
        def research_again(request: ResearchRequest) -> ResearchResponse:
            """Research a topic differently."""
            raise NotImplementedError

    assert len(pot.endpoints) == 1


def test_summon_allows_one_path_to_carry_different_methods():
    """GET /orders and POST /orders are distinct routes."""
    pot = Pot("svc")

    @pot.summon("/orders", method="GET")
    def list_orders(status: str = "open") -> str:
        """List orders."""
        return ""

    @pot.summon("/orders", method="POST")
    def place_order(item: str) -> str:
        """Place an order."""
        return ""

    assert len(pot.endpoints) == 2


def test_summon_normalizes_the_method_when_detecting_duplicates():
    pot = Pot("svc")

    @pot.summon("/orders", method="GET")
    def list_orders(status: str = "open") -> str:
        """List orders."""
        return ""

    with pytest.raises(ValueError, match="GET /orders is already registered"):

        @pot.summon("/orders", method="get")
        def list_orders_again(status: str = "open") -> str:
            """List orders again."""
            return ""


def test_summon_rejects_unimplemented_streaming():
    """The flag shipped in 0.2.0 but was never read by the runtime or the server."""
    pot = Pot("svc")

    with pytest.raises(NotImplementedError, match="stream=True is not implemented"):

        @pot.summon("/research", stream=True)
        def research(request: ResearchRequest) -> ResearchResponse:
            """Research a topic."""
            raise NotImplementedError

    assert pot.endpoints == []


def test_summon_still_accepts_the_default_non_streaming_endpoint():
    pot = Pot("svc")

    @pot.summon("/research")
    def research(request: ResearchRequest) -> ResearchResponse:
        """Research a topic."""
        raise NotImplementedError

    assert pot.endpoints[0].stream is False


def test_pot_level_capabilities_are_not_shared_between_endpoints():
    """`required` is per-endpoint state and must not leak across endpoints."""
    pot = Pot("svc", tools=[search_web_raw])

    @pot.summon("/one")
    def one(q: str) -> str:
        """One."""
        return ""

    @pot.summon("/two")
    def two(q: str) -> str:
        """Two."""
        return ""

    first, second = pot.endpoints[0].tools[0], pot.endpoints[1].tools[0]
    assert first is not second
    assert first is not pot._pot_tools[0]

    first.required = True

    assert second.required is False
    assert pot._pot_tools[0].required is False


def test_pot_accepts_a_default_model():
    pot = Pot("svc", model="anthropic:claude-sonnet-4-5")

    assert pot._runtime.default_model == "anthropic:claude-sonnet-4-5"


def test_pot_accepts_a_preconfigured_runtime():
    from summonpot.runtime import Runtime

    runtime = Runtime(model="groq:llama-3.3-70b-versatile")
    pot = Pot("svc", runtime=runtime)

    assert pot._runtime is runtime


def test_pot_rejects_both_model_and_runtime():
    from summonpot.runtime import Runtime

    with pytest.raises(TypeError, match="not both"):
        Pot("svc", model="openai:gpt-4o-mini", runtime=Runtime())
