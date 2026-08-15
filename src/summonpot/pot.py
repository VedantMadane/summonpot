"""Pot — the summoning vessel. Register endpoints, summon agents."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from summonpot._annotations import (
    get_type_str,
    reject_unresolved,
    safe_get_type_hints,
    type_name,
)
from summonpot.dependencies import Dependency
from summonpot.models import EndpointDef, ParamDef, ToolDef
from summonpot.runtime import Runtime
from summonpot.tools import build_tool_from_func


class Pot:
    """A summoning vessel for agentic endpoints.

    Example::

        from pydantic import BaseModel
        from summonpot import Pot

        class ResearchRequest(BaseModel):
            query: str

        class ResearchResponse(BaseModel):
            summary: str

        pot = Pot(tools=[search_web])

        @pot.summon("/research")
        def research_topic(request: ResearchRequest) -> ResearchResponse:
            \"\"\"Research this topic thoroughly.\"\"\"
            raise NotImplementedError

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
                if isinstance(t, ToolDef):
                    self._pot_tools.append(t)
                else:
                    self._pot_tools.append(build_tool_from_func(t))
        self._endpoints: list[EndpointDef] = []
        # (path, method) -> endpoint name, for duplicate-route detection.
        self._routes: dict[tuple[str, str], str] = {}
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

        if not path.startswith("/"):
            raise ValueError(
                f"Endpoint path {path!r} must start with '/'. A path without a "
                "leading slash registers an endpoint that no request can reach."
            )

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            endpoint_name = func.__name__
            description = inspect.getdoc(func) or ""
            if not description.strip():
                # The docstring is the endpoint's goal, not documentation. Without
                # it the agent is given an empty system prompt and told nothing
                # about what the endpoint is for.
                raise TypeError(
                    f"Endpoint {endpoint_name!r} has no docstring. The docstring is "
                    "the endpoint's goal and becomes the agent's instructions, so "
                    "it is required."
                )

            # Merge pot-level tools with endpoint-specific tools
            all_tools = list(self._pot_tools)
            if tools:
                # Convert raw functions to ToolDefs
                for t in tools:
                    if not isinstance(t, ToolDef):
                        all_tools.append(build_tool_from_func(t))
                    else:
                        all_tools.append(t)

            # Extract parameters from function signature
            sig = inspect.signature(func)
            hints = safe_get_type_hints(func)
            parameters: list[ParamDef] = []
            dependency_tools: list[ToolDef] = []
            input_model: type[BaseModel] | None = None
            for pname, param in sig.parameters.items():
                if pname in ("self", "cls"):
                    continue
                if isinstance(param.default, Dependency):
                    dependency_tool = build_tool_from_func(param.default.operation)
                    dependency_tool.required = param.default.required
                    dependency_tools.append(dependency_tool)
                    continue
                annotation = hints.get(pname, param.annotation)
                reject_unresolved(
                    annotation, where=f"parameter {pname!r}", endpoint=endpoint_name
                )
                if _is_pydantic_model(annotation):
                    input_model = annotation
                type_str = get_type_str(pname, param, hints)
                is_required = param.default is inspect.Parameter.empty
                parameters.append(
                    ParamDef(
                        name=pname,
                        type_annotation=type_str,
                        description="",
                        required=is_required,
                        default=None if is_required else param.default,
                        annotation=(
                            None
                            if annotation is inspect.Parameter.empty
                            else annotation
                        ),
                    )
                )

            if input_model is not None and len(parameters) != 1:
                raise TypeError(
                    "Pydantic endpoints must declare exactly one request parameter"
                )

            # Return type
            return_hint = hints.get("return", sig.return_annotation)
            reject_unresolved(
                return_hint, where="the return type", endpoint=endpoint_name
            )
            output_model = return_hint if _is_pydantic_model(return_hint) else None
            if return_hint is inspect.Parameter.empty or return_hint is None:
                return_type = "str"
            else:
                # Rendered with the shared helper so a generic keeps its arguments;
                # __name__ alone reduces dict[str, Response] to "dict".
                return_type = type_name(return_hint)

            endpoint_tools = [*all_tools, *dependency_tools]
            tool_names = [tool.name for tool in endpoint_tools]
            duplicate_names = sorted(
                {name for name in tool_names if tool_names.count(name) > 1}
            )
            if duplicate_names:
                raise TypeError(f"Duplicate capability name: {duplicate_names[0]}")

            # Keyed on the pair, not the path alone: GET /orders and POST /orders
            # are different routes, while a second GET /orders would be dispatched
            # to the first and silently become dead code.
            route = (path, method.upper())
            existing_name = self._routes.get(route)
            if existing_name is not None:
                raise ValueError(
                    f"{route[1]} {path} is already registered by "
                    f"{existing_name!r}. Only the first registration is reachable, "
                    "so the second would be silently dead code."
                )

            endpoint = EndpointDef(
                path=path,
                name=endpoint_name,
                description=description,
                parameters=parameters,
                return_type=return_type,
                input_model=input_model,
                output_model=output_model,
                tools=endpoint_tools,
                stream=stream,
                model=model,
            )
            self._routes[route] = endpoint_name
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


def _is_pydantic_model(annotation: Any) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)
