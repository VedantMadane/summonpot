"""Registration-time validation of typed capability contracts.

Every check here runs when the endpoint is declared, so a contract that cannot be
satisfied fails at import rather than part-way through a request. Nothing here
executes an operation or inspects a request.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from summonpot.contracts import AgentChoice, FromRequest, FromResult, Operation


def _bindable_request_fields(
    input_model: type[BaseModel] | None, parameters: list[Any]
) -> set[str]:
    """Return the names `FromRequest` may refer to for this endpoint."""
    if input_model is not None:
        return set(input_model.model_fields)
    return {parameter.name for parameter in parameters}


def _operation_signature(operation: Any) -> tuple[list[str], set[str], bool]:
    """Describe a capability's arguments.

    Returns the explicit argument names, those of them that have a default, and
    whether the operation also accepts arbitrary keyword arguments.
    """
    try:
        signature = inspect.signature(operation)
    except (TypeError, ValueError):  # pragma: no cover - exotic callables
        return [], set(), False

    names: list[str] = []
    defaulted: set[str] = set()
    accepts_extra = False
    for name, parameter in signature.parameters.items():
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_extra = True
            continue
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            continue
        names.append(name)
        if parameter.default is not inspect.Parameter.empty:
            defaulted.add(name)
    return names, defaulted, accepts_extra


def _output_fields(output: Any) -> set[str] | None:
    """Return the readable fields of a declared output type, if it has any."""
    if isinstance(output, type) and issubclass(output, BaseModel):
        return set(output.model_fields)
    return None


def validate_contracts(
    *,
    endpoint: str,
    tools: list[Any],
    input_model: type[BaseModel] | None,
    parameters: list[Any],
) -> None:
    """Check every declared contract on one endpoint.

    Raises `TypeError` naming the endpoint, the operation, and the parameter, so the
    message says what to change rather than only what is wrong.
    """
    contracts = {tool.contract for tool in tools if tool.contract is not None}
    request_fields = _bindable_request_fields(input_model, parameters)

    for tool in tools:
        contract = tool.contract
        if contract is None or contract.bind is None:
            # A bare callable, or a contract that declares no bindings, keeps the
            # existing behaviour: every argument is chosen by the model.
            continue
        _validate_bindings(
            endpoint=endpoint,
            operation=tool.name,
            contract=contract,
            declared=contracts,
            request_fields=request_fields,
            has_request_model=input_model is not None,
        )

    _reject_ordering_cycles(endpoint=endpoint, tools=tools)


def _validate_bindings(
    *,
    endpoint: str,
    operation: str,
    contract: Operation,
    declared: set[Operation],
    request_fields: set[str],
    has_request_model: bool,
) -> None:
    """Check one operation's bindings against the endpoint that declares it."""
    if contract.bind is None:  # pragma: no cover - guarded by the caller
        return
    argument_names, defaulted, accepts_extra = _operation_signature(contract.operation)

    # A binding for an argument the operation does not take is a typo that would
    # otherwise surface as a TypeError mid-request. An operation taking **kwargs
    # genuinely accepts the name, so only reject when it cannot.
    if not accepts_extra:
        for name in contract.bind:
            if name not in argument_names:
                raise TypeError(
                    f"Endpoint {endpoint!r} binds {name!r} for operation "
                    f"{operation!r}, which takes no such argument. It takes: "
                    f"{', '.join(argument_names) or 'no arguments'}."
                )

    # Declaring `bind` opts into the contract, so it has to cover every argument the
    # caller must supply. An argument the model may choose is written AgentChoice()
    # rather than left out, so a model-controlled argument is never the result of an
    # omission. An argument with a default is already determined - it takes that
    # default, and is not offered to the model - so leaving it out is a choice
    # rather than a gap.
    for name in argument_names:
        if name not in contract.bind and name not in defaulted:
            raise TypeError(
                f"Endpoint {endpoint!r} leaves argument {name!r} of operation "
                f"{operation!r} unbound, and it has no default. Every argument of an "
                "operation that declares bind must have a source; use AgentChoice() "
                "to let the model choose it."
            )

    for name, source in contract.bind.items():
        if isinstance(source, FromRequest):
            if not has_request_model and not request_fields:
                raise TypeError(
                    f"Endpoint {endpoint!r} binds {name!r} of operation "
                    f"{operation!r} to request field {source.field!r}, but the "
                    "endpoint declares no request fields."
                )
            if source.field not in request_fields:
                raise TypeError(
                    f"Endpoint {endpoint!r} binds {name!r} of operation "
                    f"{operation!r} to request field {source.field!r}, which the "
                    f"request does not declare. Available: "
                    f"{', '.join(sorted(request_fields))}."
                )
        elif isinstance(source, FromResult):
            _validate_from_result(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                source=source,
                declared=declared,
            )


def _validate_from_result(
    *,
    endpoint: str,
    operation: str,
    argument: str,
    source: FromResult,
    declared: set[Operation],
) -> None:
    """Check that a result binding names a declared operation and a readable field."""
    if source.operation not in declared:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            "a result of an operation the endpoint does not declare. Add it with "
            "Depends(...) or Required(...), or bind from one that is declared."
        )

    producer = source.operation
    if producer.output is None:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"field {source.field!r} of another operation's result, but that "
            "operation declares no output type. Give it output=... so the result can "
            "be validated before it is read."
        )

    fields = _output_fields(producer.output)
    if fields is not None and source.field not in fields:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"field {source.field!r}, which {producer.output.__name__} does not "
            f"declare. Available: {', '.join(sorted(fields))}."
        )


def _reject_ordering_cycles(*, endpoint: str, tools: list[Any]) -> None:
    """Reject a declaration whose operations cannot be put in any order.

    Both kinds of edge count: `after` states an ordering directly, and `FromResult`
    implies one, because a result cannot be read before it is produced.
    """
    edges: dict[Operation, set[Operation]] = {}
    for tool in tools:
        contract = tool.contract
        if contract is None:
            continue
        predecessors = set(contract.after)
        for source in (contract.bind or {}).values():
            if isinstance(source, FromResult):
                predecessors.add(source.operation)
            elif isinstance(source, AgentChoice) and source.from_result is not None:
                predecessors.add(source.from_result)
        edges[contract] = predecessors

    visiting: set[Operation] = set()
    done: set[Operation] = set()

    def visit(node: Operation, trail: list[Operation]) -> None:
        if node in done:
            return
        if node in visiting:
            names = " -> ".join(_name_of(n) for n in [*trail, node])
            raise TypeError(
                f"Endpoint {endpoint!r} declares operations that cannot be ordered: "
                f"{names}. Remove the cycle from after=... or the result bindings."
            )
        visiting.add(node)
        for predecessor in edges.get(node, ()):
            visit(predecessor, [*trail, node])
        visiting.discard(node)
        done.add(node)

    for contract in list(edges):
        visit(contract, [])


def _name_of(contract: Operation) -> str:
    """Render an operation for an error message."""
    return getattr(contract.operation, "__name__", type(contract.operation).__name__)
