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


def safe_get_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    """Resolve a callable's annotations.

    Only a `NameError` is tolerated, and only so the caller can report *which* name
    failed to resolve. Anything else propagates: swallowing every exception here is
    what let an endpoint silently lose its Pydantic contract.
    """
    try:
        return inspect.get_annotations(func, eval_str=True)
    except NameError:
        pass

    # One bad annotation fails the whole call, which would make every other
    # annotation look unresolvable too and report the wrong parameter. Resolve them
    # one at a time so only the genuinely broken name is left as a string.
    raw = inspect.get_annotations(func, eval_str=False)
    globalns = getattr(func, "__globals__", {})
    resolved: dict[str, Any] = {}
    for name, annotation in raw.items():
        if not isinstance(annotation, str):
            resolved[name] = annotation
            continue
        try:
            resolved[name] = eval(annotation, globalns)
        except Exception:
            resolved[name] = annotation
    return resolved


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
