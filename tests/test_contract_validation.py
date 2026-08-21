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


# --- arguments the caller need not supply ------------------------------------


def search_customers(query: str, limit: int = 10) -> Customer:
    """Search customers."""
    return Customer(customer_id=query, tier="standard")


def flexible_lookup(customer_id: str, **extra: object) -> Customer:
    """Look up a customer, accepting extra keywords."""
    return Customer(customer_id=customer_id, tier="standard")


def _register(pot: Pot, contract: Operation) -> None:
    @pot.summon("/orders")
    def create_order(request: OrderRequest, op=Required(contract)) -> OrderResponse:
        """Place an order."""
        raise NotImplementedError


def test_an_argument_with_a_default_may_be_left_unbound():
    """It is already determined: it takes the default and is not offered to the model."""
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            search_customers,
            bind={"query": FromRequest("customer_id")},
            output=Customer,
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_an_argument_with_a_default_may_still_be_bound_explicitly():
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            search_customers,
            bind={"query": FromRequest("customer_id"), "limit": AgentChoice()},
            output=Customer,
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_an_argument_without_a_default_still_has_to_be_bound():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="no default"):
        _register(
            pot,
            Operation(
                place_order,
                bind={"customer_id": FromRequest("customer_id")},
                output=OrderResponse,
            ),
        )


def test_an_operation_taking_kwargs_accepts_any_binding_name():
    """`**extra` genuinely accepts the name, so rejecting it would be a false alarm."""
    pot = Pot("svc")

    _register(
        pot,
        Operation(
            flexible_lookup,
            bind={
                "customer_id": FromRequest("customer_id"),
                "trace_id": FromContext("trace_id"),
            },
            output=Customer,
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None


def test_an_operation_without_kwargs_still_rejects_an_unknown_binding():
    pot = Pot("svc")

    with pytest.raises(TypeError, match="takes no such argument"):
        _register(
            pot,
            Operation(
                search_customers,
                bind={"query": FromRequest("customer_id"), "nope": AgentChoice()},
                output=Customer,
            ),
        )


def test_a_bound_method_operation_is_accepted():
    """The receiver is already supplied, so it is not an unbound argument."""

    class Directory:
        def __init__(self, tier: str) -> None:
            self.tier = tier

        def lookup(self, customer_id: str) -> Customer:
            """Look up a customer."""
            return Customer(customer_id=customer_id, tier=self.tier)

    pot = Pot("svc")

    _register(
        pot,
        Operation(
            Directory("gold").lookup,
            bind={"customer_id": FromRequest("customer_id")},
            output=Customer,
        ),
    )

    assert pot.endpoints[0].tools[0].contract is not None
