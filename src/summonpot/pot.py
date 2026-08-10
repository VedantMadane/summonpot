"""Pot — the summoning vessel. Register endpoints, summon agents."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from summonpot.models import EndpointDef, ParamDef
from summonpot.runtime import Runtime
from summonpot.tools import build_tool_from_func


class Pot:
    """A summoning vessel for agentic endpoints.

    Example::

        from summonpot import Pot

        pot = Pot(tools=[search_web])

        @pot.summon("/research")
        def research_topic(query: str) -> str:
            \"\"\"Research this topic thoroughly.\"\"\"

        pot.serve()
    """

    def __init__(
        self,
        name: str | None = None,
        tools: list | None = None,
    ) -> None:
        self.name = name or "summonpot"
        # Convert any raw functions to ToolDef objects
        self._pot_tools: list = []
        if tools:
            for t in tools:
                if hasattr(t, "to_openai_tool"):
                    self._pot_tools.append(t)
                else:
                    self._pot_tools.append(build_tool_from_func(t))
        self._endpoints: list[EndpointDef] = []
        self._runtime = Runtime()

    def __repr__(self) -> str:
        return f"Pot({self.name!r}, endpoints={len(self._endpoints)}, tools={len(self._pot_tools)})"

    def summon(
        self,
        path: str,
        *,
        tools: list | None = None,
        stream: bool = False,
        model: str | None = None,
        method: str = "POST",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator: summon an agent behind the given route.

        Args:
            path: URL path for the endpoint (e.g. ``/research``).
            tools: Additional tools specific to this endpoint.
            stream: Whether to stream the response.
            model: LLM model override for this endpoint.
            method: HTTP method (default POST).
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            endpoint_name = func.__name__
            description = inspect.getdoc(func) or ""

            # Merge pot-level tools with endpoint-specific tools
            all_tools = list(self._pot_tools)
            if tools:
                # Convert raw functions to ToolDefs
                for t in tools:
                    if not hasattr(t, "to_openai_tool"):
                        all_tools.append(build_tool_from_func(t))
                    else:
                        all_tools.append(t)

            # Extract parameters from function signature
            sig = inspect.signature(func)
            hints = _safe_get_type_hints(func)
            parameters: list[ParamDef] = []
            for pname, param in sig.parameters.items():
                if pname in ("self", "cls"):
                    continue
                type_str = _get_type_str(pname, param, hints)
                is_required = param.default is inspect.Parameter.empty
                parameters.append(
                    ParamDef(
                        name=pname,
                        type_annotation=type_str,
                        description="",
                        required=is_required,
                        default=None if is_required else param.default,
                    )
                )

            # Return type
            return_hint = hints.get("return", sig.return_annotation)
            if return_hint is inspect.Parameter.empty or return_hint is None:
                return_type = "str"
            elif hasattr(return_hint, "__name__"):
                return_type = return_hint.__name__
            else:
                return_type = str(return_hint)

            endpoint = EndpointDef(
                path=path,
                name=endpoint_name,
                description=description,
                parameters=parameters,
                return_type=return_type,
                tools=all_tools,
                stream=stream,
                model=model,
            )
            self._endpoints.append(endpoint)
            return func

        return decorator

    @property
    def endpoints(self) -> list[EndpointDef]:
        """Return all registered endpoints."""
        return list(self._endpoints)

    def serve(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> None:
        """Serve endpoints as an HTTP API.

        Starts a FastAPI + uvicorn server.
        Requires the ``serve`` extra: ``pip install summonpot[serve]``
        """
        self._serve_api(host, port)

    def _serve_api(self, host: str, port: int) -> None:
        try:
            import uvicorn
        except ImportError:
            raise ModuleNotFoundError(
                "uvicorn and fastapi are required for serving. "
                "Install with: pip install summonpot[serve]"
            ) from None

        from summonpot.server import build_app

        app = build_app(self)
        uvicorn.run(app, host=host, port=port)  # type: ignore[arg-type]


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
