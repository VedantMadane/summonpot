"""Typed capability contracts.

An endpoint's declaration already says *which* operations may run. These types let it
also say *where each argument's value comes from*, which is what makes the execution
path a computable property rather than a guess.

Nothing here executes: this module is vocabulary. Registration-time validation, the
capability graph, and the runtime that fills bound arguments arrive in later changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
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

    The only *argument source* a declaration does not determine: an argument bound to
    any other source is filled by the runtime and never offered to the model.

    This is a claim about one argument, not about an endpoint. An endpoint whose every
    argument is bound may still need a model — for an unresolved ordering, a choice
    between operations, or a response it cannot compose. Whether an endpoint can run
    without a model is decided by the whole capability graph together with the
    response binding, not by the absence of this source.
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


def Between(minimum: int, maximum: int) -> CallBounds:
    """Run this operation between ``minimum`` and ``maximum`` times."""
    return CallBounds(minimum=minimum, maximum=maximum)


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
    bind: Mapping[str, ArgumentSource] | None = None
    output: Any = None
    after: tuple[Operation, ...] = ()

    def __post_init__(self) -> None:
        # The bindings are the security boundary: they decide which arguments the
        # model may choose. `frozen=True` only stops the attribute being reassigned,
        # so without a snapshot the mapping stays writable through this attribute and
        # through whatever dict the caller passed in - after registration, and after
        # any validation the declaration has already passed.
        if self.bind is not None:
            object.__setattr__(self, "bind", MappingProxyType(dict(self.bind)))

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
    "Between",
    "CallBounds",
    "Exactly",
    "FromContext",
    "FromRequest",
    "FromResult",
    "Operation",
]
