"""Tests for the Pot class — endpoint registration and introspection."""

from __future__ import annotations

from summonpot import Pot
from summonpot.tools import tool


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
