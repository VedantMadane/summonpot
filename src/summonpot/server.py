"""HTTP server for summonpot — builds FastAPI routes from endpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from summonpot import __version__

if TYPE_CHECKING:
    from summonpot.pot import Pot

logger = logging.getLogger("summonpot.server")


def build_app(pot: Pot) -> Any:
    """Build a FastAPI application from a Pot instance."""
    from fastapi import FastAPI

    app = FastAPI(
        title=pot.name,
        description="An AI-native API framework. Every endpoint is an agent that runs automatically.",
        version=__version__,
    )

    for endpoint in pot.endpoints:
        route_path = endpoint.path
        method = "POST"

        if endpoint.parameters:
            if endpoint.input_model is not None:
                RequestModel = endpoint.input_model
            else:
                from pydantic import create_model

                fields: dict[str, tuple[type, Any]] = {}
                for p in endpoint.parameters:
                    field_type = _field_type(p)
                    if p.required:
                        fields[p.name] = (field_type, ...)
                    else:
                        fields[p.name] = (field_type, p.default)

                RequestModel = create_model(
                    f"{endpoint.name}Request",
                    **fields,  # pyright: ignore[reportArgumentType, reportCallIssue]
                )

            _handle_with_body = _make_body_handler(endpoint, pot, RequestModel)

            app.add_api_route(
                route_path,
                _handle_with_body,
                methods=[method],
                response_model=endpoint.output_model,
                summary=(
                    endpoint.description.split("\n")[0]
                    if endpoint.description
                    else endpoint.name
                ),
                description=endpoint.description,
            )
        else:
            _handle_without_body = _make_no_body_handler(endpoint, pot)

            app.add_api_route(
                route_path,
                _handle_without_body,
                methods=[method],
                response_model=endpoint.output_model,
                summary=(
                    endpoint.description.split("\n")[0]
                    if endpoint.description
                    else endpoint.name
                ),
                description=endpoint.description,
            )

    return app


async def _run_endpoint(pot: Any, endpoint: Any, params: dict[str, Any]) -> Any:
    """Run an endpoint, translating runtime failures into stable HTTP responses.

    Without this every failure — an unmet required capability, a provider outage, an
    exhausted budget — reached the caller as an indistinguishable bare 500.
    """
    from fastapi import HTTPException
    from pydantic_ai.exceptions import (
        ModelHTTPError,
        UnexpectedModelBehavior,
        UsageLimitExceeded,
    )

    try:
        return await pot._runtime.call(endpoint, params)
    except UsageLimitExceeded as exc:
        # Details are logged, never returned: an exception raised inside the agent
        # loop can carry rejected model output or tool-call context, and the HTTP
        # response is the one surface an untrusted caller reads.
        logger.warning(
            "Endpoint %s exceeded its usage limit", endpoint.path, exc_info=exc
        )
        raise HTTPException(
            status_code=429,
            detail="Endpoint exceeded its configured usage limit.",
        ) from exc
    except TimeoutError as exc:
        logger.warning("Endpoint %s timed out", endpoint.path, exc_info=exc)
        raise HTTPException(
            status_code=504,
            detail="Endpoint timed out before the model produced a valid response.",
        ) from exc
    except ModelHTTPError as exc:
        logger.warning(
            "Endpoint %s failed against the model provider", endpoint.path, exc_info=exc
        )
        # A provider rate limit is the one upstream status a caller can act on.
        status_code = 429 if exc.status_code == 429 else 502
        raise HTTPException(
            status_code=status_code,
            detail=f"Model provider request failed with status {exc.status_code}.",
        ) from exc
    except UnexpectedModelBehavior as exc:
        logger.warning(
            "Endpoint %s did not satisfy its contract", endpoint.path, exc_info=exc
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Model did not satisfy the endpoint contract within the retry budget."
            ),
        ) from exc


def _make_body_handler(endpoint: Any, pot: Any, request_model: type[Any]) -> Any:
    """Create a body-only route handler while retaining endpoint context in its closure."""

    async def handle(body: Any) -> Any:
        params = (
            body.model_dump(mode="json", by_alias=True)
            if hasattr(body, "model_dump")
            else body
        )
        return await _run_endpoint(pot, endpoint, params)

    handle.__annotations__["body"] = request_model
    return handle


def _make_no_body_handler(endpoint: Any, pot: Any) -> Any:
    """Create a parameter-free route handler with context retained in its closure."""

    async def handle() -> Any:
        return await _run_endpoint(pot, endpoint, {})

    return handle


def _field_type(param: Any) -> Any:
    """Resolve the request-body field type for one endpoint parameter.

    Prefers the resolved annotation object so unions stay nullable, ``Any`` stays
    permissive, and a generic keeps its element type. Falls back to parsing the
    display string only when no annotation could be resolved.
    """
    annotation = param.annotation
    if annotation is None or isinstance(annotation, str):
        return _str_to_type(param.type_annotation)
    return annotation


def _str_to_type(type_str: str) -> type:
    """Convert a type annotation string to a Python type.

    Fallback for parameters whose annotation could not be resolved to an object.
    """
    mapping: dict[str, type] = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
        "Any": str,
        "None": type(None),
    }
    base = type_str.split("[")[0].split("|")[0].strip()
    return mapping.get(base, str)
