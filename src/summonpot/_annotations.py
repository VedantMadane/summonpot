"""Shared annotation inspection for endpoints and capabilities.

Endpoint registration and capability construction ask the same three questions of a
signature, so the answers live here once rather than in two copies that can drift.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


def type_name(tp: Any) -> str:
    """Render an annotation as a short display string."""
    if hasattr(tp, "__origin__"):
        origin = tp.__origin__
        args = tp.__args__
        if origin is list and args:
            return f"list[{type_name(args[0])}]"
        if origin is dict and len(args) >= 2:
            return f"dict[{type_name(args[0])}, {type_name(args[1])}]"
        if origin is tuple:
            return f"tuple[{', '.join(type_name(a) for a in args)}]"
        return type_name(origin)
    if tp is type(None):
        return "None"
    if hasattr(tp, "__name__"):
        return tp.__name__
    return str(tp)


def get_type_str(
    pname: str,
    param: inspect.Parameter,
    hints: dict[str, Any],
) -> str:
    """Render one parameter's annotation, preferring resolved hints."""
    if pname in hints:
        return type_name(hints[pname])
    if param.annotation is not inspect.Parameter.empty:
        return type_name(param.annotation)
    return "str"


# A quoted reference may nest ("Request" -> 'Request' -> Request); the bound stops
# a pathological self-referential alias from looping.
_MAX_FORWARD_REF_DEPTH = 5


def _resolve_annotation(annotation: Any, globalns: dict[str, Any]) -> Any:
    """Evaluate an annotation, following nested quoted forward references.

    Under ``from __future__ import annotations`` an explicitly quoted annotation such
    as ``request: "Request"`` is stored as the source text ``'"Request"'``. Evaluating
    that once yields the *string* ``'Request'`` rather than the class, so a single
    pass cannot tell a valid forward reference from an unresolvable name.

    Returns the resolved object, or the name that failed to resolve so the caller can
    report it.
    """
    current = annotation
    for _ in range(_MAX_FORWARD_REF_DEPTH):
        if not isinstance(current, str):
            return current
        try:
            current = eval(current, globalns)
        except Exception:
            return current
    return current


def safe_get_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolve a callable's annotations.

    Each annotation is resolved independently: one unresolvable name would otherwise
    fail the whole call and make every healthy annotation beside it look broken too,
    so the error would name the wrong parameter.
    """
    globalns = getattr(func, "__globals__", {})
    return {
        name: _resolve_annotation(annotation, globalns)
        for name, annotation in inspect.get_annotations(func, eval_str=False).items()
    }


def reject_unresolved(annotation: Any, *, where: str, endpoint: str) -> None:
    """Fail loudly when an annotation could not be resolved to a type.

    An unresolved annotation is still a string, so nothing downstream can tell a
    Pydantic model from a plain value. Degrading to an untyped endpoint would discard
    exactly the contract the framework exists to enforce.
    """
    if isinstance(annotation, str):
        raise TypeError(
            f"Could not resolve the annotation {annotation!r} for {where} of "
            f"endpoint {endpoint!r}. summonpot builds the request and response "
            "contracts from these annotations and will not fall back to an untyped "
            "endpoint. Import the type at runtime rather than only under "
            "TYPE_CHECKING, and declare it at module scope."
        )
