# Declarative capability endpoints

A summonpot endpoint is a declaration, not a Python handler.

```python
@pot.summon("/research")
def research(
    request: ResearchRequest,
    sources=Required(load_sources),
    ranking=Depends(rank_sources),
) -> ResearchResponse:
    """Research using only the declared operations."""
    raise NotImplementedError
```

The signature defines four things:

- The Pydantic request model is the JSON contract.
- The docstring is the fixed endpoint goal.
- Dependencies are the complete set of deterministic operations exposed to the agent.
- The Pydantic return model is the required output contract.

## Dependency semantics

`Depends(operation)` exposes an exact operation that the agent may call.

`Required(operation)` exposes an exact operation and prevents successful final output until that operation has completed.

Required use is checked by runtime state. It is not only written into the prompt.

## Deterministic and agentic execution

Capabilities are deterministic operations in both modes. The difference is whether execution still has an unresolved legal choice:

```text
one complete path → deterministic execution
bounded choice remains → agentic execution
no legal path → typed deterministic error
```

The public endpoint declaration stays the same. The fixed docstring goal and validated request determine the work; callers do not send an `action` field or select an agent framework. Automatic deterministic endpoint execution is planned—the current runtime still executes `@pot.summon` requests through the provider-neutral agent loop.

Dependency parameters are declaration-only. They do not appear in the HTTP request body or OpenAPI request schema, and the decorated function body is never executed.

## What the boundary does and does not cover

The endpoint agent receives its declared dependencies and no ambient application access. An operation can contain deterministic business logic or a safe database adapter. Raw database sessions, connections, cursors, ORM registries, shells, and arbitrary SQL execution should not be exposed.

For databases, the target adapter API accepts exact prepared operations rather than broad infrastructure objects:

- a developer-declared SQLAlchemy `Select`, `Insert`, `Update`, or `Delete` statement;
- a fixed parameterized SQLite statement specification;
- explicit bind sources such as validated request fields;
- a typed projection or write receipt;
- a framework-owned session or connection factory that is never agent-visible.

The agent receives the operation's typed callable schema—not the statement, SQL text, ORM metadata, session, engine, connection, or cursor. It cannot edit the query or execute another one.

### Arguments are not yet constrained

The closed set covers *which* operations the agent may call. It does not yet cover *what it may pass to them*.

Request data reaches the model as text, and the model chooses the arguments for every `Depends` and `Required` operation. So today:

- an argument may be influenced by caller-supplied request content;
- `Required(operation)` checks that the operation ran, not that it ran with request-derived values;
- an operation can be called with values the caller never sent.

Write each capability so it validates its own inputs and enforces its own authorization, exactly as you would for an operation reachable from an untrusted caller. Do not rely on the agent to pass only sensible arguments.

Constraining argument sources—request data, prior operation results, framework context, or explicitly agent-controlled values—is milestone 1 on the [roadmap](../ROADMAP.md).

Strict SQLAlchemy and SQLite operation objects are planned and not yet shipped. See the target API examples in the README and the implementation sequence in the roadmap.
