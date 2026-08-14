"""Tests for the shared annotation helpers.

These branches were previously duplicated between pot.py and tools.py, and several
were untested in both copies.
"""

from __future__ import annotations

import inspect

import pytest

from summonpot._annotations import get_type_str, safe_get_type_hints, type_name


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (str, "str"),
        (type(None), "None"),
        (list[str], "list[str]"),
        (dict[str, int], "dict[str, int]"),
        (tuple[int, str], "tuple[int, str]"),
        (list[dict[str, int]], "list[dict[str, int]]"),
        (list, "list"),
    ],
)
def test_type_name_renders_generics(annotation, expected):
    assert type_name(annotation) == expected


def test_type_name_falls_back_to_str_for_unnamed_annotations():
    assert type_name(int | None) == "int | None"


def test_get_type_str_prefers_resolved_hints_over_raw_annotations():
    def endpoint(value: list[int]) -> None: ...

    parameters = inspect.signature(endpoint).parameters
    hints = safe_get_type_hints(endpoint)

    assert get_type_str("value", parameters["value"], hints) == "list[int]"


def test_get_type_str_defaults_to_str_when_unannotated():
    def endpoint(value) -> None: ...

    parameters = inspect.signature(endpoint).parameters

    assert get_type_str("value", parameters["value"], {}) == "str"


def test_safe_get_type_hints_resolves_string_annotations():
    def endpoint(value: int) -> str: ...

    assert safe_get_type_hints(endpoint) == {"value": int, "return": str}


def test_safe_get_type_hints_follows_nested_quoted_forward_references():
    """PEP 563 stores `x: "int"` as the source text '"int"', not as 'int'."""

    def endpoint(value): ...

    endpoint.__annotations__ = {"value": '"int"', "return": '"str"'}

    assert safe_get_type_hints(endpoint) == {"value": int, "return": str}


def test_safe_get_type_hints_reports_the_name_that_failed():
    def endpoint(value): ...

    endpoint.__annotations__ = {"value": '"NeverDefined"'}

    # The failing *name* comes back, not the quoted source, so the error reads well.
    assert safe_get_type_hints(endpoint)["value"] == "NeverDefined"
