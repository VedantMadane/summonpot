"""Tool registration and built-in tools for summonpot."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

from summonpot.models import ParamDef, ToolDef


def tool(
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[..., Any]], ToolDef]:
    """Decorator to define a summonpot tool from a plain function.

    Example::

        from summonpot.tools import tool

        @tool(name="search_web", description="Search the web for information")
        def search_web(query: str) -> list[dict]:
            \"\"\"Search the web.\"\"\"
            return [{"title": "result"}]
    """

    def decorator(func: Callable[..., Any]) -> ToolDef:
        tool_name = name or capability_name(func)
        tool_desc = description or inspect.getdoc(_unwrap_partials(func)) or ""
        sig = inspect.signature(func)
        hints = _safe_get_type_hints(_annotation_source(func))
        params: list[ParamDef] = []
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            type_str = _get_type_str(pname, param, hints)
            is_required = param.default is inspect.Parameter.empty
            description_text = ""
            # Try to get param description from docstring
            params.append(
                ParamDef(
                    name=pname,
                    type_annotation=type_str,
                    description=description_text,
                    required=is_required,
                    default=None if is_required else param.default,
                )
            )
        return ToolDef(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            fn=func,
        )

    return decorator


def _unwrap_partials(func: Callable[..., Any]) -> Callable[..., Any]:
    target = func
    while isinstance(target, functools.partial):
        target = target.func
    return target


def capability_name(func: Callable[..., Any]) -> str:
    """Return the name a capability is exposed to the model under.

    Plain functions use their own name. ``functools.partial`` objects use the name of
    the function they wrap, and callable instances — the natural way to bind a
    connection or configuration into a capability — use their class name.
    """
    target = _unwrap_partials(func)
    if not callable(target):
        raise TypeError(
            "Capability must be callable, got "
            f"{type(target).__name__!r}. Pass a function, a functools.partial, "
            "or an object with a __call__ method."
        )
    return getattr(target, "__name__", None) or type(target).__name__


def _annotation_source(func: Callable[..., Any]) -> Any:
    """Return the object carrying the annotations for ``func``.

    ``inspect.get_annotations`` rejects partials and plain instances, so unwrap to
    the underlying function or to the class's ``__call__``.
    """
    target = _unwrap_partials(func)
    if inspect.isfunction(target) or inspect.ismethod(target):
        return target
    if callable(target):
        # A callable instance carries its annotations on the class's __call__.
        return type(target).__call__
    return target


def build_tool_from_func(func: Callable[..., Any]) -> ToolDef:
    """Build a ToolDef from a raw function (no decorator)."""
    tool_name = capability_name(func)
    # Read the docstring off the unwrapped target: a partial would otherwise
    # describe itself to the model with functools.partial's own docstring.
    tool_desc = inspect.getdoc(_unwrap_partials(func)) or ""
    sig = inspect.signature(func)
    hints = _safe_get_type_hints(_annotation_source(func))
    params: list[ParamDef] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        type_str = _get_type_str(pname, param, hints)
        is_required = param.default is inspect.Parameter.empty
        params.append(
            ParamDef(
                name=pname,
                type_annotation=type_str,
                description="",
                required=is_required,
                default=None if is_required else param.default,
            )
        )
    return ToolDef(
        name=tool_name,
        description=tool_desc,
        parameters=params,
        fn=func,
    )


def _get_type_str(
    pname: str,
    param: inspect.Parameter,
    hints: dict[str, Any],
) -> str:
    if pname in hints:
        return _type_name(hints[pname])
    if param.annotation is not inspect.Parameter.empty:
        return _type_name(param.annotation)
    return "str"


def _type_name(tp: Any) -> str:
    """Convert a type annotation to a short string name."""
    if hasattr(tp, "__origin__"):
        origin = tp.__origin__
        args = tp.__args__
        if origin is list and args:
            return f"list[{_type_name(args[0])}]"
        if origin is dict and len(args) >= 2:
            return f"dict[{_type_name(args[0])}, {_type_name(args[1])}]"
        if origin is tuple:
            return f"tuple[{', '.join(_type_name(a) for a in args)}]"
        return _type_name(origin)
    if tp is type(None):
        return "None"
    if hasattr(tp, "__name__"):
        return tp.__name__
    return str(tp)


def _safe_get_type_hints(func: Callable[..., Any]) -> dict[str, Any]:
    try:
        return inspect.get_annotations(func, eval_str=True)
    except Exception:
        return inspect.get_annotations(func, eval_str=False)
