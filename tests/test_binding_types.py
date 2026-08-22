"""Conservative type checking of bound arguments.

The rule is asymmetric on purpose: a binding is rejected only when it can be *proven*
wrong. Anything unresolved, `Any`, or a shape the comparison does not model is
accepted, because a guard that refuses a valid declaration is worse than one that
misses an invalid one — the invalid one still fails later with a real error, while
the valid one can never be written at all.

The acceptance tests here matter as much as the rejections.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

import pytest
from pydantic import BaseModel, Field

from summonpot import (
    AgentChoice,
    FromContext,
    FromRequest,
    FromResult,
    Operation,
    Pot,
    Required,
)
from summonpot._types import is_compatible, selectable_item_type


class Person(BaseModel):
    name: str


class Customer(Person):
    tier: str


class Request(BaseModel):
    customer_id: str
    quantity: int
    ratio: float
    tags: list[str]
    anything: Any
    optional_note: str | None = None


class Response(BaseModel):
    ok: bool


def _register(pot: Pot, *contracts: Operation) -> None:
    """Register an endpoint declaring the given contracts."""
    import inspect as _inspect

    def endpoint(request: Request, **_: object) -> Response:
        """Do the thing."""
        raise NotImplementedError

    params = [
        _inspect.Parameter(
            "request", _inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request
        )
    ]
    params += [
        _inspect.Parameter(
            f"op{index}",
            _inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Required(contract),
            annotation=object,
        )
        for index, contract in enumerate(contracts)
    ]
    endpoint.__signature__ = _inspect.Signature(  # type: ignore[attr-defined]
        params, return_annotation=Response
    )
    endpoint.__annotations__ = {"request": Request, "return": Response}
    pot.summon("/thing")(endpoint)


# --- the comparison itself ---------------------------------------------------


@pytest.mark.parametrize(
    ("supplied", "wanted", "compatible"),
    [
        (str, str, True),
        (int, str, False),
        (Customer, Person, True),
        (Person, Customer, False),
        (int, float, True),
        (bool, int, True),
        (float, int, False),
        (str, str | None, True),
        (int | str, str, False),
        (str | None, str | None, True),
        (list[int], list[int], True),
        (list[int], list[str], False),
        (list[int], Sequence[int], True),
        (Literal["a", "b"], str, True),
        (Literal[1], str, False),
    ],
)
def test_provable_relationships(supplied, wanted, compatible):
    assert is_compatible(supplied, wanted) is compatible


@pytest.mark.parametrize(
    ("supplied", "wanted"),
    [
        (Any, str),
        (str, Any),
        (None, str),
        (str, None),
        ("UnresolvedName", str),
        (str, "UnresolvedName"),
        (object, int),
        (Annotated[str, Field(min_length=3)], str),
        (str, Annotated[str, Field(min_length=3)]),
    ],
    ids=[
        "any-source",
        "any-target",
        "unannotated-source",
        "unannotated-target",
        "forward-ref-source",
        "forward-ref-target",
        "object",
        "annotated-source",
        "annotated-target",
    ],
)
def test_the_unprovable_is_accepted(supplied, wanted):
    """Not proven wrong is not the same as proven right, and only the first rejects."""
    assert is_compatible(supplied, wanted) is True


# --- bindings, end to end ----------------------------------------------------


def wants_str(customer_id: str) -> Customer:
    """Take a string."""
    return Customer(name="n", tier="t")


def wants_int(quantity: int) -> Customer:
    """Take an integer."""
    return Customer(name="n", tier="t")


def test_a_request_field_of_the_wrong_type_is_rejected():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="incompatible"):
        _register(
            pot,
            Operation(
                wants_str,
                bind={"customer_id": FromRequest("quantity")},
                output=Customer,
            ),
        )


def test_a_request_field_of_the_right_type_is_accepted():
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            wants_str, bind={"customer_id": FromRequest("customer_id")}, output=Customer
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_a_widening_request_field_is_accepted():
    """int satisfies float; the numeric tower is not a mismatch."""

    def wants_float(ratio: float) -> Customer:
        """Take a float."""
        return Customer(name="n", tier="t")

    pot = Pot("svc")

    _register(
        pot,
        Operation(
            wants_float, bind={"ratio": FromRequest("quantity")}, output=Customer
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_an_untyped_request_field_is_accepted():
    """`Any` proves nothing, so it cannot disprove anything either."""
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            wants_str, bind={"customer_id": FromRequest("anything")}, output=Customer
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_a_result_field_of_the_wrong_type_is_rejected():
    producer = Operation(
        wants_str, bind={"customer_id": FromRequest("customer_id")}, output=Customer
    )
    pot = Pot("svc")

    with pytest.raises(TypeError, match="incompatible"):
        _register(
            pot,
            producer,
            Operation(
                wants_int,
                bind={"quantity": FromResult(producer, "tier")},
                output=Customer,
            ),
        )


def test_a_result_field_of_the_right_type_is_accepted():
    def consume_tier(customer_id: str) -> Customer:
        """Take a string."""
        return Customer(name="n", tier="t")

    producer = Operation(
        wants_str, bind={"customer_id": FromRequest("customer_id")}, output=Customer
    )
    pot = Pot("svc")

    _register(
        pot,
        producer,
        Operation(
            consume_tier,
            bind={"customer_id": FromResult(producer, "tier")},
            output=Customer,
        ),
    )

    assert len(pot.endpoints[0].tools) == 2


def test_a_context_binding_is_never_rejected():
    """Framework context has no type registry, so nothing about it is provable."""
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            wants_str, bind={"customer_id": FromContext("trace_id")}, output=Customer
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


# --- what a model may be asked to choose from --------------------------------


@pytest.mark.parametrize(
    ("output", "selectable"),
    [
        (list[Customer], True),
        (set[str], True),
        (tuple[str, ...], True),
        (Sequence[str], True),
        (str, False),
        (bytes, False),
        (dict[str, int], False),
        (Customer, False),
        (Any, True),
    ],
)
def test_selectable_shapes(output, selectable):
    assert selectable_item_type(output)[0] is selectable


def test_a_choice_from_a_collection_is_accepted():
    def list_tiers(customer_id: str) -> list[str]:
        """List tiers."""
        return ["a"]

    producer = Operation(
        list_tiers, bind={"customer_id": FromRequest("customer_id")}, output=list[str]
    )
    pot = Pot("svc")

    _register(
        pot,
        producer,
        Operation(
            wants_str,
            bind={"customer_id": AgentChoice(from_result=producer, item_type=str)},
            output=Customer,
        ),
    )

    assert len(pot.endpoints[0].tools) == 2


def test_a_choice_whose_item_type_contradicts_the_collection_is_rejected():
    def list_tiers(customer_id: str) -> list[str]:
        """List tiers."""
        return ["a"]

    producer = Operation(
        list_tiers, bind={"customer_id": FromRequest("customer_id")}, output=list[str]
    )
    pot = Pot("svc")

    with pytest.raises(TypeError, match="returns a collection of"):
        _register(
            pot,
            producer,
            Operation(
                wants_int,
                bind={"quantity": AgentChoice(from_result=producer, item_type=int)},
                output=Customer,
            ),
        )
