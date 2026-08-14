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
    """Resolve a callable's annotations, falling back to the unevaluated strings."""
    try:
        return inspect.get_annotations(func, eval_str=True)
    except Exception:
        return inspect.get_annotations(func, eval_str=False)
