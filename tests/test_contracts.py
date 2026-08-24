"""Tests for typed capability contracts.

Step 01 of the typed-contract work: this is vocabulary, so the tests pin the shape of
the declaration and the rules that reject a contradictory one. Nothing consumes the
bindings yet.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from summonpot import (
    AgentChoice,
    AtLeast,
    AtMost,
    Between,
    CallBounds,
    Depends,
    Exactly,
    FromContext,
    FromRequest,
    FromResult,
    Operation,
    Pot,
    Required,
)


class Customer(BaseModel):
    customer_id: str
    tier: str


class OrderRequest(BaseModel):
    customer_id: str
    sku: str


class OrderResponse(BaseModel):
    order_id: str


def lookup_customer(customer_id: str) -> Customer:
    """Look up a customer."""
    return Customer(customer_id=customer_id, tier="standard")


def place_order(customer_id: str, sku: str) -> OrderResponse:
    """Place an order."""
    return OrderResponse(order_id="o1")


# --- the declaration ---------------------------------------------------------


def test_operation_carries_bindings_and_output():
    contract = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )

    assert contract.operation is lookup_customer
    assert contract.bind == {"customer_id": FromRequest("customer_id")}
    assert contract.output is Customer


def test_argument_sources_compare_by_value():
    """Two identical bindings are the same binding; the graph relies on this."""
    assert FromRequest("customer_id") == FromRequest("customer_id")
    assert FromRequest("customer_id") != FromRequest("account_id")
    assert FromContext("request_id") == FromContext("request_id")


def test_from_result_names_the_producing_operation():
    lookup = Operation(lookup_customer, output=Customer)
    source = FromResult(lookup, "tier")

    assert source.operation is lookup
    assert source.field == "tier"


def test_agent_choice_is_the_only_undetermined_source():
    """Every other source resolves to one value; this is what makes a path provable."""
    determined = [
        FromRequest("x"),
        FromResult(Operation(lookup_customer), "y"),
        FromContext("z"),
    ]

    assert all(not isinstance(s, AgentChoice) for s in determined)
    assert isinstance(AgentChoice(), AgentChoice)


# --- reuse -------------------------------------------------------------------


def test_with_bind_returns_a_separate_operation():
    """Reuse creates a second contract rather than an endpoint-local override."""
    by_customer = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    by_account = by_customer.with_bind(customer_id=FromRequest("account_id"))

    assert by_account is not by_customer
    assert by_customer.bind == {"customer_id": FromRequest("customer_id")}
    assert by_account.bind == {"customer_id": FromRequest("account_id")}
    # The underlying callable and the rest of the contract are shared.
    assert by_account.operation is lookup_customer
    assert by_account.output is Customer


# --- call bounds -------------------------------------------------------------


@pytest.mark.parametrize(
    ("bounds", "minimum", "maximum"),
    [
        (Exactly(1), 1, 1),
        (AtLeast(2), 2, None),
        (AtMost(3), 0, 3),
    ],
)
def test_call_bound_helpers(bounds, minimum, maximum):
    assert (bounds.minimum, bounds.maximum) == (minimum, maximum)


def test_unsatisfiable_bounds_are_rejected():
    with pytest.raises(ValueError, match="unsatisfiable"):
        CallBounds(minimum=2, maximum=1)


def test_depends_defaults_to_optional_and_unbounded():
    assert Depends(lookup_customer).bounds == CallBounds(minimum=0, maximum=None)


def test_required_stays_at_least_once():
    """Not exactly once: narrowing it would change what existing endpoints mean."""
    assert Required(lookup_customer).bounds == CallBounds(minimum=1, maximum=None)


def test_calls_tightens_the_marker():
    assert Required(lookup_customer, calls=Exactly(1)).bounds == CallBounds(1, 1)
    assert Depends(lookup_customer, calls=AtMost(2)).bounds == CallBounds(0, 2)


def test_calls_may_not_contradict_depends():
    with pytest.raises(ValueError, match="Use Required"):
        Depends(lookup_customer, calls=AtLeast(1))


def test_calls_may_not_contradict_required():
    with pytest.raises(ValueError, match=r"unsatisfiable|Use Depends"):
        Required(lookup_customer, calls=AtMost(0))


# --- integration with the endpoint ------------------------------------------


def test_an_operation_registers_like_a_bare_callable():
    contract = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest, customer=Required(contract)
    ) -> OrderResponse:
        """Place an order for this customer."""
        ...

    (tool,) = pot.endpoints[0].tools
    assert tool.name == "lookup_customer"
    assert tool.required is True
    assert tool.contract is contract
    assert tool.bounds == CallBounds(minimum=1)


def test_a_bare_callable_still_registers_with_no_contract():
    """The contract is opt-in; endpoints written before it keep working unchanged."""
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest, customer=Required(lookup_customer)
    ) -> OrderResponse:
        """Place an order for this customer."""
        ...

    (tool,) = pot.endpoints[0].tools
    assert tool.contract is None
    assert tool.bounds == CallBounds(minimum=1)


def test_a_maximum_does_not_relax_required_below_once():
    """`calls` tightens the marker; it must never let a Required operation be skipped."""
    bounds = Required(lookup_customer, calls=AtMost(3)).bounds

    assert bounds == CallBounds(minimum=1, maximum=3)
    assert bounds.describe() == "between 1 and 3"


def test_a_maximum_leaves_depends_optional():
    assert Depends(lookup_customer, calls=AtMost(3)).bounds == CallBounds(0, 3)


# --- the bindings are the security boundary ----------------------------------


def test_registered_bindings_cannot_be_changed_through_the_contract():
    """`frozen=True` stops reassignment; it does not stop mutating the mapping.

    The endpoint stores this exact object, so a writable mapping would let the
    security boundary be moved after registration and after validation.
    """
    contract = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )

    with pytest.raises(TypeError):
        contract.bind["customer_id"] = AgentChoice()  # type: ignore[index]


def test_registered_bindings_cannot_be_changed_through_the_callers_mapping():
    """The contract snapshots the mapping rather than storing it by reference."""
    declared = {"customer_id": FromRequest("customer_id")}
    contract = Operation(lookup_customer, bind=declared, output=Customer)
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest, customer=Required(contract)
    ) -> OrderResponse:
        """Place an order for this customer."""
        ...

    declared["customer_id"] = FromRequest("attacker_controlled")

    registered = pot.endpoints[0].tools[0].contract
    assert registered is not None
    assert registered.bind == {"customer_id": FromRequest("customer_id")}


def test_with_bind_returns_an_immutable_snapshot_too():
    contract = Operation(
        lookup_customer, bind={"customer_id": FromRequest("customer_id")}
    )
    derived = contract.with_bind(customer_id=FromRequest("account_id"))

    with pytest.raises(TypeError):
        derived.bind["customer_id"] = AgentChoice()  # type: ignore[index]
    assert contract.bind == {"customer_id": FromRequest("customer_id")}


# --- the public surface is complete ------------------------------------------


def test_call_bounds_is_importable_from_the_package_root():
    """The helpers cannot express every interval, so the type itself is public."""
    assert CallBounds(minimum=2, maximum=3).describe() == "between 2 and 3"
    assert Between(2, 3) == CallBounds(minimum=2, maximum=3)


def test_declared_ordering_cannot_be_changed_through_the_callers_sequence():
    """`after` is graph data, read exactly as the bindings are."""
    audit = Operation(lookup_customer)
    ordering = [audit]
    contract = Operation(place_order, after=ordering)

    ordering.append(Operation(lookup_customer))

    assert contract.after == (audit,)
    assert isinstance(contract.after, tuple)


# --- graph node semantics ----------------------------------------------------


def test_operations_are_hashable_whether_or_not_they_are_bound():
    """Step 03 uses these as set and dict keys; it cannot depend on `bind`."""
    unbound = Operation(lookup_customer)
    bound = Operation(lookup_customer, bind={"customer_id": FromRequest("customer_id")})
    ordered = Operation(place_order, after=[unbound])

    assert {unbound, bound, ordered} == {unbound, bound, ordered}
    assert len({unbound, bound, ordered}) == 3


def test_operations_are_distinct_nodes_even_when_declared_alike():
    """Two declarations are two nodes, so FromResult names one of them unambiguously."""
    first = Operation(lookup_customer, bind={"customer_id": FromRequest("customer_id")})
    second = Operation(
        lookup_customer, bind={"customer_id": FromRequest("customer_id")}
    )

    assert first == first
    assert first != second
    assert FromResult(first, "tier") == FromResult(first, "tier")
    assert FromResult(first, "tier") != FromResult(second, "tier")
