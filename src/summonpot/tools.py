"""Tool registration and built-in tools for summonpot."""

from __future__ import annotations

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
        tool_name = name or func.__name__
        tool_desc = description or inspect.getdoc(func) or ""
        sig = inspect.signature(func)
        hints = _safe_get_type_hints(func)
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


def build_tool_from_func(func: Callable[..., Any]) -> ToolDef:
    """Build a ToolDef from a raw function (no decorator)."""
    tool_name = func.__name__
    tool_desc = inspect.getdoc(func) or ""
    sig = inspect.signature(func)
    hints = _safe_get_type_hints(func)
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
