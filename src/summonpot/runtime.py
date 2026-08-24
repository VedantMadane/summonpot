"""Provider-agnostic agent runtime for summonpot."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.models import Model
from pydantic_ai.usage import UsageLimits

from summonpot.models import EndpointDef

ModelSpec = Model | str


@dataclass
class _EndpointRun:
    """State for one endpoint call, passed to the agent as its dependencies."""

    completed_required: set[str] = field(default_factory=set)


def _tracked_operation(tool: Any) -> Any:
    """Wrap a capability so a successful call is recorded on the run state."""

    async def execute(*args: Any, **kwargs: Any) -> Any:
        # The run context arrives first positionally, whatever it is named in the
        # declared signature below.
        ctx, *capability_args = args
        result = await tool.call(*capability_args, **kwargs)
        if tool.required:
            ctx.deps.completed_required.add(tool.name)
        return result

    # Describe the capability explicitly rather than with functools.wraps. wraps only
    # produces a usable schema when the target is a plain function: for a partial or
    # a callable instance it leaves the model reading this wrapper's own annotations
    # against the wrong module.
    signature, annotations = _resolved_signature(tool.fn)

    # An exact application capability may legitimately have a field called `ctx`, so
    # the injected parameter takes a name that cannot collide with a real one.
    context_name = "ctx"
    while context_name in signature.parameters:
        context_name = f"_{context_name}"

    context_parameter = inspect.Parameter(
        context_name,
        inspect.Parameter.POSITIONAL_ONLY,
        annotation=RunContext[_EndpointRun],
    )
    execute.__name__ = tool.name
    execute.__doc__ = tool.description or None
    execute.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=[context_parameter, *signature.parameters.values()]
    )
    execute.__annotations__ = {
        context_name: RunContext[_EndpointRun],
        **annotations,
    }
    return execute


class Runtime:
    """Execute summonpot endpoints through a provider-agnostic agent engine."""

    def __init__(
        self,
        model: ModelSpec | None = None,
        *,
        retries: int = 1,
        usage_limits: UsageLimits | None = None,
        timeout: float | None = None,
    ) -> None:
        self._model = model
        self.retries = retries
        self.usage_limits = usage_limits
        self.timeout = timeout
        self._agents: dict[
            tuple[str, str, str], tuple[EndpointDef, Agent[_EndpointRun, Any]]
        ] = {}

    @property
    def default_model(self) -> ModelSpec:
        """Resolve the default model at call time.

        Resolved lazily so that setting ``SUMMONPOT_MODEL`` after the module
        defining the ``Summon`` application is imported still takes effect. Reading it in
        ``__init__`` made the variable silently useless in that very common case.
        """
        configured = self._model or os.environ.get(
            "SUMMONPOT_MODEL", "openai:gpt-4o-mini"
        )
        return _normalize_model(configured)

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
        agent = self._agent_for(endpoint)
        run = _EndpointRun()

        message = self._build_user_message(endpoint, params)
        # asyncio.timeout(None) is a no-op, so one path covers both cases. The
        # deadline releases the caller promptly even while a synchronous capability
        # occupies a worker thread; that thread is simply left to finish.
        async with asyncio.timeout(self.timeout):
            result = await agent.run(message, deps=run, usage_limits=self.usage_limits)
        output = result.output

        if endpoint.output_model is not None:
            return output
        if endpoint.return_type.lower() not in ("str", "string", "any"):
            try:
                return json.loads(output)
            except (json.JSONDecodeError, TypeError):
                return output
        return output

    def _agent_for(self, endpoint: EndpointDef) -> Agent[_EndpointRun, Any]:
        """Return the cached agent for an endpoint, building it on first use.

        Tool and output schemas do not change between requests, so rebuilding them
        per call was pure overhead. The resolved model is part of the cache key
        because it is resolved lazily and may change between calls.
        """
        model = self.model_for(endpoint)
        key = (endpoint.path, endpoint.name, str(model))
        cached = self._agents.get(key)
        if cached is not None and cached[0] is endpoint:
            return cached[1]

        agent = self._build_agent(endpoint, model)
        self._agents[key] = (endpoint, agent)
        return agent

    def _build_agent(
        self, endpoint: EndpointDef, model: ModelSpec
    ) -> Agent[_EndpointRun, Any]:
        """Construct the agent for an endpoint.

        Required-capability tracking lives on the per-run dependency object rather
        than in a closure, which is what allows the agent itself to be reused.
        """
        tools = [
            Tool(
                _tracked_operation(tool),
                name=tool.name,
                description=tool.description,
                takes_ctx=True,
            )
            for tool in endpoint.tools
        ]
        agent = Agent(
            model,
            output_type=endpoint.output_model or str,
            system_prompt=endpoint.description,
            tools=tools,
            retries=self.retries,
            deps_type=_EndpointRun,
        )

        @agent.output_validator
        def require_declared_operations(
            ctx: RunContext[_EndpointRun], output: Any
        ) -> Any:
            missing = {
                tool.name
                for tool in endpoint.tools
                if tool.required and tool.name not in ctx.deps.completed_required
            }
            if missing:
                names = ", ".join(sorted(missing))
                raise ModelRetry(
                    f"Required capabilities must run before final output: {names}"
                )
            return output

        return agent

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


# Built-in models that need no provider and no API key. Prefixing these would
# send them to a provider that then demands credentials, which is what made
# SUMMONPOT_MODEL=test unusable for trying summonpot out.
PROVIDERLESS_MODELS = frozenset({"test"})


def _normalize_model(model: ModelSpec) -> ModelSpec:
    """Keep explicit providers and preserve legacy OpenAI model names."""
    if not isinstance(model, str) or ":" in model:
        return model
    if model in PROVIDERLESS_MODELS:
        return model
    return f"openai:{model}"
