"""Registration-time validation of typed capability contracts.

Every check here runs when the endpoint is declared, so a contract that cannot be
satisfied fails at import rather than part-way through a request. Nothing here
executes an operation or inspects a request.

There is deliberately no cycle detection. `Operation` is frozen and snapshots both
`bind` and `after`, and an edge can only name a node that already exists, so a cycle
cannot be built through the public API — only by bypassing immutability with
`object.__setattr__`. If a later representation can express one, detection belongs
with the graph that can.
"""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel

from summonpot._types import describe, is_compatible, selectable_item_type
from summonpot.contracts import AgentChoice, FromRequest, FromResult, Operation

_VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)


def _bindable_request_fields(
    input_model: type[BaseModel] | None, parameters: list[Any]
) -> set[str]:
    """Return the names `FromRequest` may refer to for this endpoint."""
    if input_model is not None:
        return set(input_model.model_fields)
    return {parameter.name for parameter in parameters}


def _request_annotations(
    input_model: type[BaseModel] | None, parameters: list[Any]
) -> dict[str, Any]:
    """Return the endpoint's request field types, keyed by the name bindings use."""
    if input_model is not None:
        return {
            name: field.annotation for name, field in input_model.model_fields.items()
        }
    return {parameter.name: parameter.annotation for parameter in parameters}


def _readable_fields(output: Any) -> set[str] | None:
    """Return the fields a result exposes, or None if it exposes none statically."""
    if isinstance(output, type) and issubclass(output, BaseModel):
        return set(output.model_fields)
    return None


def _argument_annotations(tool: Any) -> dict[str, Any]:
    """Return an operation's resolved argument types, keyed by name.

    Read from the normalized ParamDef list rather than by re-inspecting the callable,
    so this agrees with the arguments the model is actually offered for a bound
    method, a callable object or a partial.
    """
    return {p.name: p.annotation for p in tool.parameters}


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
    declared = {tool.contract for tool in tools if tool.contract is not None}
    request_fields = _bindable_request_fields(input_model, parameters)

    for tool in tools:
        contract = tool.contract
        if contract is None:
            continue
        # `after` states an ordering against another operation, so that operation has
        # to be one this endpoint declares. Checked even without bindings, because
        # ordering is part of the capability graph in its own right.
        for predecessor in contract.after:
            _require_declared(
                endpoint=endpoint,
                operation=tool.name,
                referenced=predecessor,
                declared=declared,
                what="orders itself after",
            )
        if contract.bind is None:
            # A contract that declares no bindings keeps the existing behaviour:
            # every argument is chosen by the model.
            continue
        _validate_bindings(
            endpoint=endpoint,
            operation=tool.name,
            contract=contract,
            declared=declared,
            request_fields=request_fields,
            argument_types=_argument_annotations(tool),
            request_types=_request_annotations(input_model, parameters),
        )


def _require_declared(
    *,
    endpoint: str,
    operation: str,
    referenced: Operation,
    declared: set[Operation],
    what: str,
) -> None:
    """Reject a reference to an operation outside the endpoint's capability set.

    The endpoint's declared operations are its whole capability set. A reference to
    anything else would put an operation into the graph that the endpoint never
    exposed.
    """
    if referenced not in declared:
        name = getattr(
            referenced.operation, "__name__", type(referenced.operation).__name__
        )
        raise TypeError(
            f"Endpoint {endpoint!r}: operation {operation!r} {what} {name!r}, which "
            "the endpoint does not declare. Add it with Depends(...) or "
            "Required(...), or reference one that is declared."
        )


def _validate_bindings(
    *,
    endpoint: str,
    operation: str,
    contract: Operation,
    declared: set[Operation],
    request_fields: set[str],
    argument_types: dict[str, Any],
    request_types: dict[str, Any],
) -> None:
    """Check one operation's bindings against the endpoint that declares it."""
    bind = contract.bind or {}
    signature = inspect.signature(contract.operation)

    # A contracted operation may not take *args or **kwargs. Their schema is
    # open-ended - pydantic-ai emits `additionalProperties: true` - so the model could
    # pass keys the contract never named, which is the authority a typed capability
    # exists to close. A bare callable is unaffected; wrap the operation in one with
    # explicit parameters to give it a contract.
    variadic = [
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind in _VARIADIC
    ]
    if variadic:
        raise TypeError(
            f"Endpoint {endpoint!r}: operation {operation!r} declares bind but takes "
            f"{', '.join('*' + n if signature.parameters[n].kind is inspect.Parameter.VAR_POSITIONAL else '**' + n for n in variadic)}. "
            "A contracted operation needs explicit parameters, because a variadic "
            "signature lets the model pass arguments the contract never named. Wrap "
            "it in a function with named parameters."
        )

    argument_names = list(signature.parameters)
    defaulted = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }

    # A binding for an argument the operation does not take is a typo that would
    # otherwise surface as a TypeError mid-request.
    for name in bind:
        if name not in argument_names:
            raise TypeError(
                f"Endpoint {endpoint!r} binds {name!r} for operation {operation!r}, "
                f"which takes no such argument. It takes: "
                f"{', '.join(argument_names) or 'no arguments'}."
            )

    # Declaring `bind` opts into the contract, so it has to cover every argument the
    # caller must supply. An argument the model may choose is written AgentChoice()
    # rather than left out, so a model-controlled argument is never the result of an
    # omission. An argument with a default is already determined - it takes that
    # default, and is not offered to the model - so leaving it out is a choice.
    for name in argument_names:
        if name not in bind and name not in defaulted:
            raise TypeError(
                f"Endpoint {endpoint!r} leaves argument {name!r} of operation "
                f"{operation!r} unbound, and it has no default. Every argument of an "
                "operation that declares bind must have a source; use AgentChoice() "
                "to let the model choose it."
            )

    for name, source in bind.items():
        if isinstance(source, FromRequest):
            _validate_from_request(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                source=source,
                request_fields=request_fields,
            )
            _require_compatible(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                wanted=argument_types.get(name),
                supplied=request_types.get(source.field),
                origin=f"request field {source.field!r}",
            )
        elif isinstance(source, FromResult):
            _require_declared(
                endpoint=endpoint,
                operation=operation,
                referenced=source.operation,
                declared=declared,
                what=f"binds {name!r} from",
            )
            _validate_result_field(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                source=source,
            )
            _require_compatible(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                wanted=argument_types.get(name),
                supplied=_result_field_type(source),
                origin=(
                    f"field {source.field!r} of {_operation_name(source.operation)!r}"
                ),
            )
        elif isinstance(source, AgentChoice) and source.from_result is not None:
            _require_declared(
                endpoint=endpoint,
                operation=operation,
                referenced=source.from_result,
                declared=declared,
                what=f"offers {name!r} from",
            )
            # Offering a result to the model puts it into agent context, so it has
            # the same prerequisite as reading a field from it: the producer must
            # declare an output type, or the value reaches the model unvalidated.
            # No field check here - AgentChoice names no field.
            _require_validatable_output(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                producer=source.from_result,
            )
            _require_selectable(
                endpoint=endpoint,
                operation=operation,
                argument=name,
                source=source,
            )


def _operation_name(contract: Operation) -> str:
    """Render an operation for an error message."""
    return getattr(contract.operation, "__name__", type(contract.operation).__name__)


def _result_field_type(source: FromResult) -> Any:
    """Return the declared type of the output field a binding reads."""
    output = source.operation.output
    if isinstance(output, type) and issubclass(output, BaseModel):
        field = output.model_fields.get(source.field)
        if field is not None:
            return field.annotation
    return None


def _require_compatible(
    *,
    endpoint: str,
    operation: str,
    argument: str,
    wanted: Any,
    supplied: Any,
    origin: str,
) -> None:
    """Reject a binding whose value provably cannot satisfy the argument.

    Only a definite mismatch is rejected. An unresolved annotation, `Any`, or a shape
    the comparison does not model is accepted, because refusing what cannot be proven
    would block valid declarations.
    """
    if is_compatible(supplied, wanted):
        return
    raise TypeError(
        f"Endpoint {endpoint!r} binds {origin} ({describe(supplied)}) to argument "
        f"{argument!r} of operation {operation!r} ({describe(wanted)}). Those types "
        "are incompatible."
    )


def _require_selectable(
    *, endpoint: str, operation: str, argument: str, source: AgentChoice
) -> None:
    """Reject offering the model a choice from a result it cannot choose from."""
    producer = source.from_result
    if producer is None:  # pragma: no cover - guarded by the caller
        return

    selectable, item_type = selectable_item_type(producer.output)
    if not selectable:
        raise TypeError(
            f"Endpoint {endpoint!r} offers argument {argument!r} of operation "
            f"{operation!r} as a choice from the result of "
            f"{_operation_name(producer)!r}, typed "
            f"{describe(producer.output)}. A choice is made from a list, set, tuple "
            "or sequence; that type is not a collection of selectable items."
        )

    if source.item_type is not None and not is_compatible(item_type, source.item_type):
        raise TypeError(
            f"Endpoint {endpoint!r} offers argument {argument!r} of operation "
            f"{operation!r} as a choice of {describe(source.item_type)}, but "
            f"{_operation_name(producer)!r} returns a collection of "
            f"{describe(item_type)}."
        )


def _validate_from_request(
    *,
    endpoint: str,
    operation: str,
    argument: str,
    source: FromRequest,
    request_fields: set[str],
) -> None:
    """Check that a request binding names a field the endpoint declares."""
    if not request_fields:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"request field {source.field!r}, but the endpoint declares no request "
            "fields."
        )
    if source.field not in request_fields:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"request field {source.field!r}, which the request does not declare. "
            f"Available: {', '.join(sorted(request_fields))}."
        )


def _require_validatable_output(
    *, endpoint: str, operation: str, argument: str, producer: Operation
) -> None:
    """Reject consuming a result the producer never gave a type to.

    A result reaches agent context whether it is read from or offered as a choice,
    and the invariant is the same either way: it must be validated against a declared
    type before it gets there.
    """
    if producer.output is None:
        name = getattr(
            producer.operation, "__name__", type(producer.operation).__name__
        )
        raise TypeError(
            f"Endpoint {endpoint!r} consumes the result of {name!r} for argument "
            f"{argument!r} of operation {operation!r}, but {name!r} declares no "
            "output type. Give it output=... so the result can be validated before "
            "it is used."
        )


def _validate_result_field(
    *, endpoint: str, operation: str, argument: str, source: FromResult
) -> None:
    """Check that a result binding reads a field the producer's output declares."""
    producer = source.operation
    _require_validatable_output(
        endpoint=endpoint, operation=operation, argument=argument, producer=producer
    )

    fields = _readable_fields(producer.output)
    if fields is None:
        name = getattr(producer.output, "__name__", repr(producer.output))
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"field {source.field!r} of a result typed {name}, whose fields cannot be "
            "checked. Declare output= as a Pydantic model to read a field from it."
        )
    if source.field not in fields:
        raise TypeError(
            f"Endpoint {endpoint!r} binds {argument!r} of operation {operation!r} to "
            f"field {source.field!r}, which {producer.output.__name__} does not "
            f"declare. Available: {', '.join(sorted(fields))}."
        )
