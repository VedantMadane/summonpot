"""Provider-agnostic agent runtime for summonpot."""

from __future__ import annotations

import inspect
import json
import os
from typing import Any

from pydantic_ai import Agent, ModelRetry, Tool
from pydantic_ai.models import Model

from summonpot.models import EndpointDef

ModelSpec = Model | str


class Runtime:
    """Execute summonpot endpoints through a provider-agnostic agent engine."""

    def __init__(
        self,
        model: ModelSpec | None = None,
        *,
        retries: int = 1,
    ) -> None:
        configured_model = model or os.environ.get(
            "SUMMONPOT_MODEL", "openai:gpt-4o-mini"
        )
        self.default_model = _normalize_model(configured_model)
        self.retries = retries

    def model_for(self, endpoint: EndpointDef) -> ModelSpec:
        """Resolve an endpoint override or the runtime's default model."""
        if endpoint.model is not None:
            return _normalize_model(endpoint.model)
        return self.default_model

    async def call(
        self,
        endpoint: EndpointDef,
        params: dict[str, Any],
    ) -> Any:
        """Run an endpoint with provider-neutral tools and typed output."""
        output_type: Any = endpoint.output_model or str
        completed_required: set[str] = set()

        def tracked_operation(tool: Any) -> Any:
            async def execute(*args: Any, **kwargs: Any) -> Any:
                result = await tool.call(*args, **kwargs)
                if tool.required:
                    completed_required.add(tool.name)
                return result

            # Describe the capability explicitly rather than with functools.wraps.
            # wraps only produces a usable schema when the target is a plain
            # function: for a partial or a callable instance it leaves the model
            # reading this wrapper's own annotations against the wrong module.
            signature, annotations = _resolved_signature(tool.fn)
            execute.__name__ = tool.name
            execute.__doc__ = tool.description or None
            execute.__signature__ = signature  # type: ignore[attr-defined]
            execute.__annotations__ = annotations
            return execute

        tools = [
            Tool(
                tracked_operation(tool),
                name=tool.name,
                description=tool.description,
                takes_ctx=False,
            )
            for tool in endpoint.tools
        ]
        agent = Agent(
            self.model_for(endpoint),
            output_type=output_type,
            system_prompt=endpoint.description,
            tools=tools,
            retries=self.retries,
        )

        @agent.output_validator
        def require_declared_operations(output: Any) -> Any:
            missing = {
                tool.name
                for tool in endpoint.tools
                if tool.required and tool.name not in completed_required
            }
            if missing:
                names = ", ".join(sorted(missing))
                raise ModelRetry(
                    f"Required capabilities must run before final output: {names}"
                )
            return output

        result = await agent.run(self._build_user_message(endpoint, params))
        output = result.output

        if endpoint.output_model is not None:
            return output
        if endpoint.return_type.lower() not in ("str", "string", "any"):
            try:
                return json.loads(output)
            except (json.JSONDecodeError, TypeError):
                return output
        return output

    def _build_user_message(
        self,
        endpoint: EndpointDef,
        params: dict[str, Any],
    ) -> str:
        """Build a provider-neutral user message from endpoint parameters."""
        parts = [f"Endpoint: {endpoint.path}"]
        if params:
            parts.append("Parameters:")
            for key, value in params.items():
                parts.append(f"  {key}: {json.dumps(value, default=str)}")
        return "\n".join(parts)


def _resolved_signature(target: Any) -> tuple[inspect.Signature, dict[str, Any]]:
    """Return a capability's signature and annotations as real type objects.

    Resolving here means the wrapper carries no string annotations for the provider
    layer to evaluate, so a capability keeps its schema regardless of which module
    it was defined in or whether it is a function, a partial, or a callable object.
    """
    try:
        signature = inspect.signature(target, eval_str=True)
    except (TypeError, NameError):
        signature = inspect.signature(target)

    annotations: dict[str, Any] = {
        name: parameter.annotation
        for name, parameter in signature.parameters.items()
        if parameter.annotation is not inspect.Parameter.empty
    }
    if signature.return_annotation is not inspect.Signature.empty:
        annotations["return"] = signature.return_annotation
    return signature, annotations


def _normalize_model(model: ModelSpec) -> ModelSpec:
    """Keep explicit providers and preserve legacy OpenAI model names."""
    if not isinstance(model, str) or ":" in model:
        return model
    return f"openai:{model}"
