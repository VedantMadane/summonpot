"""Registration-time validation of typed capability contracts.

Step 02: a contract that cannot be satisfied fails when the endpoint is declared,
not part-way through a request. Half of these tests assert that a *valid* declaration
is still accepted, because every guard this project has added needed that as much as
it needed the rejection case.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from summonpot import (
    AgentChoice,
    FromContext,
    FromRequest,
    FromResult,
    Operation,
    Pot,
    Required,
)


class OrderRequest(BaseModel):
    customer_id: str
    sku: str


class Customer(BaseModel):
    customer_id: str
    tier: str


class OrderResponse(BaseModel):
    order_id: str


def lookup_customer(customer_id: str) -> Customer:
    """Look up a customer."""
    return Customer(customer_id=customer_id, tier="standard")


def place_order(customer_id: str, tier: str, sku: str) -> OrderResponse:
    """Place an order."""
    return OrderResponse(order_id="o1")


def record_audit(customer_id: str) -> Customer:
    """Record an audit entry."""
    return Customer(customer_id=customer_id, tier="standard")


# --- valid declarations are still accepted -----------------------------------


def test_a_bare_callable_needs_no_contract():
    """The contract is opt-in; endpoints written before it keep working."""
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest, customer=Required(lookup_customer)
    ) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError

    assert pot.endpoints[0].tools[0].contract is None


def test_an_operation_may_declare_an_output_without_bindings():
    """Declaring no bindings means what it means today: the model chooses."""
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest,
        customer=Required(Operation(lookup_customer, output=Customer)),
    ) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError

    assert pot.endpoints[0].tools[0].contract is not None


def test_a_complete_chain_of_bindings_is_accepted():
    lookup = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest,
        customer=Required(lookup),
        order=Required(
            Operation(
                place_order,
                bind={
                    "customer_id": FromRequest("customer_id"),
                    "tier": FromResult(lookup, "tier"),
                    "sku": FromRequest("sku"),
                },
                output=OrderResponse,
            )
        ),
    ) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError

    assert len(pot.endpoints[0].tools) == 2


@pytest.mark.parametrize("source", [AgentChoice(), FromContext("user_id")])
def test_non_request_sources_are_accepted(source):
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest,
        customer=Required(
            Operation(lookup_customer, bind={"customer_id": source}, output=Customer)
        ),
    ) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError

    assert pot.endpoints[0].tools[0].contract is not None


def test_from_request_resolves_against_a_scalar_endpoint():
    """An endpoint without a request model still declares bindable field names."""
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        customer_id: str,
        customer=Required(
            Operation(
                lookup_customer,
                bind={"customer_id": FromRequest("customer_id")},
                output=Customer,
            )
        ),
    ) -> str:
        """Place an order."""
        raise NotImplementedError

    assert pot.endpoints[0].tools[0].contract is not None


def test_a_diamond_of_dependencies_is_not_a_cycle():
    """Two operations may share a predecessor."""
    first = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    second = Operation(
        record_audit,
        bind={"customer_id": FromResult(first, "customer_id")},
        output=Customer,
    )
    third = Operation(
        place_order,
        bind={
            "customer_id": FromResult(first, "customer_id"),
            "tier": FromResult(first, "tier"),
            "sku": FromRequest("sku"),
        },
        output=OrderResponse,
        after=[second],
    )
    pot = Pot("svc")

    @pot.summon("/orders")
    def create_order(
        request: OrderRequest,
        a=Required(first),
        b=Required(second),
        c=Required(third),
    ) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError

    assert len(pot.endpoints[0].tools) == 3


# --- invalid declarations fail at registration -------------------------------


def test_a_binding_for_an_unknown_argument_is_rejected():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="takes no such argument"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            customer=Required(
                Operation(
                    lookup_customer,
                    bind={"custmer_id": FromRequest("customer_id")},
                    output=Customer,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_a_partially_bound_operation_is_rejected():
    """An omitted argument must not silently become model-controlled."""
    pot = Pot("svc")

    with pytest.raises(TypeError, match="unbound"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            order=Required(
                Operation(
                    place_order,
                    bind={"customer_id": FromRequest("customer_id")},
                    output=OrderResponse,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_from_request_naming_a_missing_field_is_rejected():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="request does not declare"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            customer=Required(
                Operation(
                    lookup_customer,
                    bind={"customer_id": FromRequest("custmer_id")},
                    output=Customer,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_from_result_on_an_undeclared_operation_is_rejected():
    elsewhere = Operation(lookup_customer, output=Customer)
    pot = Pot("svc")

    with pytest.raises(TypeError, match="does not declare"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            order=Required(
                Operation(
                    place_order,
                    bind={
                        "customer_id": FromRequest("customer_id"),
                        "tier": FromResult(elsewhere, "tier"),
                        "sku": FromRequest("sku"),
                    },
                    output=OrderResponse,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_from_result_on_an_operation_without_an_output_is_rejected():
    """A result cannot be read before it can be validated."""
    lookup = Operation(
        lookup_customer, bind={"customer_id": FromRequest("customer_id")}
    )
    pot = Pot("svc")

    with pytest.raises(TypeError, match="declares no output type"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            customer=Required(lookup),
            order=Required(
                Operation(
                    place_order,
                    bind={
                        "customer_id": FromRequest("customer_id"),
                        "tier": FromResult(lookup, "tier"),
                        "sku": FromRequest("sku"),
                    },
                    output=OrderResponse,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_from_result_naming_a_missing_output_field_is_rejected():
    lookup = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    pot = Pot("svc")

    with pytest.raises(TypeError, match="Customer does not declare"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest,
            customer=Required(lookup),
            order=Required(
                Operation(
                    place_order,
                    bind={
                        "customer_id": FromRequest("customer_id"),
                        "tier": FromResult(lookup, "teir"),
                        "sku": FromRequest("sku"),
                    },
                    output=OrderResponse,
                )
            ),
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_a_cycle_between_two_operations_is_rejected():
    first = Operation(lookup_customer, output=Customer)
    second = Operation(
        record_audit,
        bind={"customer_id": FromResult(first, "customer_id")},
        output=Customer,
    )
    object.__setattr__(
        first, "bind", {"customer_id": FromResult(second, "customer_id")}
    )
    pot = Pot("svc")

    with pytest.raises(TypeError, match="cannot be ordered"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest, a=Required(first), b=Required(second)
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError


def test_a_cycle_error_names_the_whole_trail():
    """The message has to say which operations form the loop."""
    first = Operation(
        lookup_customer,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
    )
    second = Operation(
        record_audit,
        bind={"customer_id": FromRequest("customer_id")},
        output=Customer,
        after=[first],
    )
    object.__setattr__(first, "after", (second,))
    pot = Pot("svc")

    with pytest.raises(TypeError, match="lookup_customer -> record_audit"):

        @pot.summon("/orders")
        def create_order(
            request: OrderRequest, a=Required(first), b=Required(second)
        ) -> OrderResponse:
            """Place an order."""
            raise NotImplementedError
