"""Typed capability contracts.

An endpoint's declaration already says *which* operations may run. These types let it
also say *where each argument's value comes from*, which is what makes the execution
path a computable property rather than a guess.

Nothing here executes: this module is vocabulary. Registration-time validation, the
capability graph, and the runtime that fills bound arguments arrive in later changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

# ---------------------------------------------------------------------------
# Argument sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArgumentSource:
    """Where one operation argument's value comes from."""


@dataclass(frozen=True)
class FromRequest(ArgumentSource):
    """Take the value from a field of the validated request model."""

    field: str


@dataclass(frozen=True)
class FromResult(ArgumentSource):
    """Take the value from a field of an earlier operation's validated output.

    The output is validated against the producing operation's ``output`` type before
    it can be read here, so a later argument can never be bound to an unvalidated
    value.
    """

    operation: Operation
    field: str


@dataclass(frozen=True)
class FromContext(ArgumentSource):
    """Take the value from framework-owned state rather than from the caller."""

    key: str


@dataclass(frozen=True)
class AgentChoice(ArgumentSource):
    """Let the model choose the value.

    The only source that is not determined by the declaration, and therefore the only
    reason an endpoint needs a model at all. An argument bound to any other source is
    filled by the runtime and never offered to the model.
    """

    from_result: Operation | None = None
    item_type: Any = None


# ---------------------------------------------------------------------------
# Call bounds
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CallBounds:
    """How many times an operation may run within one request."""

    minimum: int = 0
    maximum: int | None = None

    def __post_init__(self) -> None:
        if self.minimum < 0:
            raise ValueError("Call bounds cannot require a negative number of calls.")
        if self.maximum is not None and self.maximum < self.minimum:
            raise ValueError(
                f"Call bounds are unsatisfiable: maximum {self.maximum} is below "
                f"minimum {self.minimum}."
            )

    def describe(self) -> str:
        """Render the bounds for an error message."""
        if self.maximum is None:
            return f"at least {self.minimum}"
        if self.minimum == self.maximum:
            return f"exactly {self.minimum}"
        return f"between {self.minimum} and {self.maximum}"


def Exactly(count: int) -> CallBounds:
    """Run this operation exactly ``count`` times."""
    return CallBounds(minimum=count, maximum=count)


def AtLeast(count: int) -> CallBounds:
    """Run this operation at least ``count`` times."""
    return CallBounds(minimum=count)


def AtMost(count: int) -> CallBounds:
    """Run this operation at most ``count`` times."""
    return CallBounds(maximum=count)


# ---------------------------------------------------------------------------
# Operation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Operation:
    """A capability together with the contract governing how it may be called.

    Declared away from the endpoint so the endpoint signature stays a declaration
    rather than a configuration object::

        lookup_by_customer_id = Operation(
            lookup_customer,
            bind={"customer_id": FromRequest("customer_id")},
            output=Customer,
        )

        @pot.summon("/orders")
        def place_order(
            request: OrderRequest,
            customer=Required(lookup_by_customer_id),
        ) -> OrderResponse:
            \"\"\"Place an order for this customer.\"\"\"
            raise NotImplementedError
    """

    operation: Callable[..., Any]
    bind: dict[str, ArgumentSource] | None = None
    output: Any = None
    after: tuple[Operation, ...] = ()

    def with_bind(self, **bindings: ArgumentSource) -> Operation:
        """Return a copy of this operation with some bindings replaced.

        For the case where two endpoints need the same callable reading differently
        named request fields. The endpoint still receives a complete ``Operation``;
        this only avoids restating the parts that do not change.
        """
        merged = {**(self.bind or {}), **bindings}
        return replace(self, bind=merged)


__all__ = [
    "AgentChoice",
    "ArgumentSource",
    "AtLeast",
    "AtMost",
    "CallBounds",
    "Exactly",
    "FromContext",
    "FromRequest",
    "FromResult",
    "Operation",
]
