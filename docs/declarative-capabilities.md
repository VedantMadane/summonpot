# Declarative capability endpoints

A summonpot endpoint is a declaration, not a Python handler.

The opening fragment focuses on the declaration shape and assumes the application-specific
request models and operations are defined elsewhere. For a standalone runnable application,
start with the [quick start](../README.md#quick-start).

```python
from summonpot import Depends, Required, Summon


summon = Summon("research-api")


@summon("/research")
def research(
    request: ResearchRequest,
    sources=Required(load_sources),
    ranking=Depends(rank_sources),
) -> ResearchResponse:
    """Research using only the declared operations."""
    ...
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

## Typed operation dataflow

`Operation` adds a validated declaration of where capability arguments are intended to
come from without adding configuration to `@summon(...)`:

```python
from summonpot import AgentChoice, FromRequest, FromResult, Operation


customer = Operation(
    load_customer,
    bind={"customer_id": FromRequest("customer_id")},
    output=CustomerRecord,
)
ticket = Operation(
    create_ticket,
    bind={
        "customer_id": FromResult(customer, "customer_id"),
        "priority": AgentChoice(),
        "summary": AgentChoice(),
    },
    output=TicketReceipt,
    after=(customer,),
)
```

`FromRequest` names validated request data. `FromResult` names a field on a declared
producer's typed output. `FromContext` names framework-owned state. `AgentChoice` is the
explicit model-controlled source. Registration rejects incomplete bindings, missing
fields, undeclared producers, and types known to be incompatible. Dependency cycles are
structurally unrepresentable through the immutable public `Operation` API rather than
discovered by a separate cycle detector.

The declarations are immutable and shipped today. Runtime binding injection, ordering,
and maximum/exact call-count enforcement are not: the current model runtime still supplies
capability arguments. See the executable
[`06_support_service` example](../examples/06_support_service/app.py) for a complete typed
chain and its explicit current-runtime boundary.

## Deterministic and agentic execution

Capabilities are deterministic operations in both modes. The difference is whether execution still has an unresolved legal choice:

```text
one complete path → deterministic execution
bounded choice remains → agentic execution
no legal path → typed deterministic error
```

The public endpoint declaration stays the same. The fixed docstring goal and validated request determine the work; callers do not send an `action` field or select an agent framework. Automatic deterministic endpoint execution is planned—the current runtime still executes `@summon` requests through the provider-neutral agent loop.

Dependency parameters are declaration-only. They do not appear in the HTTP request body
or OpenAPI request schema. The ellipsis is the complete declaration body, and direct calls
to a registered declaration are rejected; execution goes through the generated endpoint.

## What the boundary does and does not cover

The endpoint agent receives its declared dependencies and no ambient application access. An operation can contain deterministic business logic or a safe database adapter. Raw database sessions, connections, cursors, ORM registries, shells, and arbitrary SQL execution should not be exposed.

For databases, the target adapter API accepts exact prepared operations rather than broad infrastructure objects:

- a developer-declared SQLAlchemy `Select`, `Insert`, `Update`, or `Delete` statement;
- a fixed parameterized SQLite statement specification;
- explicit bind sources such as validated request fields;
- a typed projection or write receipt;
- a framework-owned session or connection factory that is never agent-visible.

The agent receives the operation's typed callable schema—not the statement, SQL text, ORM metadata, session, engine, connection, or cursor. It cannot edit the query or execute another one.

### Arguments are not yet constrained at runtime

The closed set covers *which* operations the agent may call. `Operation.bind` now records
and validates intended argument sources, but the current runtime does not yet use those
declarations to constrain *what the model may pass to them*.

Request data reaches the model as text, and the model chooses the arguments for every `Depends` and `Required` operation. So today:

- an argument may be influenced by caller-supplied request content;
- `Required(operation)` checks that the operation ran, not that it ran with request-derived values;
- an operation can be called with values the caller never sent.

Write each capability so it validates its own inputs and enforces its own authorization, exactly as you would for an operation reachable from an untrusted caller. Do not rely on the agent to pass only sensible arguments.

Enforcing declared argument sources at runtime—injecting request data, prior operation
results, framework context, or explicitly agent-controlled values—is milestone 1 on the
[roadmap](../ROADMAP.md).

Strict SQLAlchemy and SQLite operation objects are planned and not yet shipped. See the target API examples in the README and the implementation sequence in the roadmap.
