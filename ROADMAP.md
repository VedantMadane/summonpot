# summonpot roadmap

summonpot is building toward one endpoint contract:

```text
Pydantic request model
+ fixed endpoint goal
+ exact deterministic capabilities
+ Pydantic response model
= executable endpoint
```

The endpoint body is declarative and is never the handler. Request JSON carries business data, not an action selector. The same contract can support deterministic execution when one complete path exists or agentic execution when a bounded choice remains. In either mode, execution may use only the capabilities declared by the endpoint.

## Shipped foundation

The current release line provides:

- Pydantic request validation and OpenAPI request schemas.
- Pydantic response contracts with local final validation.
- Provider-neutral model selection and structured output.
- Optional deterministic operations through `Depends(operation)`.
- Runtime-enforced mandatory operations through `Required(operation)`.
- A closed endpoint capability set: undeclared operations are unavailable.
- Declarative dependency parameters that never become HTTP fields.
- Bounded retries when model output is invalid or required use is missing.
- Configurable request, token, cost, and timeout limits for each endpoint call.
- Redacted HTTP mappings for usage limits, timeouts, provider failures, and unsatisfied model contracts.
- GET, POST, PUT, PATCH, DELETE, and HEAD routing with validated body or query contracts.
- A keyless test model for exercising routing and capability wiring without provider credentials.
- Installable coding-agent skills describing the endpoint contract, for Claude Code, Cursor, Windsurf, GitHub Copilot, Cline, and OpenAI Codex.
- Immutable `Operation` declarations with `FromRequest`, `FromResult`, `FromContext`, and `AgentChoice` argument sources.
- Declarative call bounds and ordering references without adding decorator configuration.
- Registration-time validation for complete bindings, request and result references, operation ordering, selectable collections, and provable type incompatibility.
- Python 3.11–3.13 CI, package builds, and expanded runtime/CLI coverage.

### 0.5.0 boundary

Version 0.5.0 ships the vocabulary and registration checks for typed operation dataflow.
It does not yet inject those bindings during execution. The current model runtime still
supplies capability arguments, and every reachable capability must validate and authorize
its inputs exactly as it did before 0.5.0.

## Next milestones

The ordering below reflects technical dependencies, not promised release dates.

### 1. Bound execution and capability graph

Make the validated declarations control execution:

- Inject `FromRequest`, `FromResult`, and `FromContext` values instead of offering those arguments to the model.
- Offer only `AgentChoice` values to the model, constrained to the declared selectable collection.
- Validate operation outputs before a later operation can read them.
- Enforce declared ordering and call bounds during each request.
- Build the per-endpoint capability graph needed to distinguish complete paths, bounded choices, and impossible paths.
- Keep unknown type relationships conservative without letting unknown branches erase known contradictions.

### 2. Exact database operations

Add optional adapters for prepared operations without exposing database authority:

```text
prepared SQLAlchemy statement or fixed SQLite specification
→ framework-owned adapter and connection/session lifecycle
→ Required(...) or Depends(...) endpoint capability
→ typed callable schema visible to the executor
```

Target declarations will pass the bounded operation object into the endpoint—not a session, connection, or arbitrary query function:

```python
customer=Required(
    SQLAlchemyOperation(
        statement=customer_select,
        bind={"customer_id": FromRequest("customer_id")},
        output=CustomerView,
    )
)

receipt=Required(
    SQLiteOperation(
        sql=cancel_order_sql,
        bind={"order_id": FromRequest("order_id")},
        output=CancelReceipt,
        exactly_one_row=True,
    )
)
```

- SQLAlchemy `Select`, `Insert`, `Update`, and `Delete` statement objects.
- Fixed parameterized SQLite operation specifications.
- Framework-owned sessions, connections, transactions, and serialization.
- Typed projections and affected-row constraints.
- No raw `Session`, `Engine`, `Connection`, cursor, editable SQL, or natural-language-to-SQL capability.

### 3. Deterministic execution compiler

Select the least-powerful sufficient execution path for each validated request:

```text
one complete operation path
→ deterministic executor

unresolved legal choice or binding
→ direct agent runtime

no valid path
→ typed deterministic error
```

This decision will use the fixed endpoint goal, validated request, capability graph, and operation results. Callers will not send an `action` field or select an agent framework.

The public declaration remains `@pot.summon` in every mode. Endpoint authors will not maintain separate deterministic and agentic handlers for the same goal:

- A balance endpoint with one exact account lookup and calculation path can run deterministically.
- An order-fulfilment endpoint can run deterministically when only one valid option remains.
- The same order endpoint can use the direct agent runtime when several declared substitutions are valid and a semantic choice remains.
- No executor may add capabilities, weaken validation, or change the response contract.

### 4. Receipts and broader stable failures

Extend the current redacted HTTP handling so authoritative success claims and operation failures depend on deterministic evidence:

- Typed write receipts.
- Successful-write requirements before accepting success responses.
- Idempotency and transaction policies.
- Typed mappings for authorization, missing records, conflicts, database failures, and exhausted recovery paths, building on the shipped 429/502/504 mappings for usage limits, provider failures, and timeouts.
- Declared recovery paths that cannot expand endpoint authority.

### 5. Optional execution harnesses

Keep the public endpoint contract stable while adding larger internal executors when the request genuinely needs them:

- Direct typed tool loops for normal synchronous endpoints.
- Workspace execution for files, planning, long context, or subagents.
- Durable execution for background, resumable, or long-running work.

Summonpot—not the caller or model—will choose the smallest eligible harness. Changing the harness must never grant additional capabilities.

## Non-goals

- Requiring users to configure agent graphs, chains, planners, or framework-specific agents.
- Turning `@pot.summon` into a traditional handler decorator.
- One endpoint or method for every possible action when one fixed goal can naturally orchestrate bounded capabilities.
- Accepting caller-provided action names as a substitute for endpoint intent.
- Exposing raw database sessions, arbitrary SQL, shell access, filesystem access, or ambient application authority.
- Treating provider-native structured output as a replacement for local validation.

## Design invariant

```text
No declared capability
=
No authority to perform the action
```

The execution harness may evolve. The endpoint's request model, goal, capabilities, and response model remain authoritative.
