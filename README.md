# summonpot

<p align="center">
  <img src="summonpot.png" alt="SummonPot" width="600">
</p>

[![CI](https://github.com/tugrulguner/summonpot/actions/workflows/ci.yml/badge.svg)](https://github.com/tugrulguner/summonpot/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/summonpot)](https://pypi.org/project/summonpot/)
[![Python versions](https://img.shields.io/pypi/pyversions/summonpot)](https://pypi.org/project/summonpot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**One API framework for typed endpoints with bounded agentic execution.**

summonpot defines typed HTTP endpoints from four things: a Pydantic request model, a fixed goal, a closed set of exact capabilities, and a Pydantic response model. Today, every `@pot.summon` request runs through the provider-neutral agent runtime. Application-owned operations can be optional or mandatory, and the runtime enforces mandatory use before accepting locally validated output.

The target architecture keeps this public contract unchanged while adding a deterministic executor. When all operation arguments and result bindings resolve to one complete legal path, the framework will skip the model. When a real bounded choice remains, the agent runtime will choose and order only declared operations. Callers will never send an `action` or select the executor.

**The function signature is the endpoint.** Its request model, docstring goal, declared capabilities, and response type form the complete executable contract. You do not write orchestration or business logic under the endpoint:

```text
request model
+ fixed goal in the docstring
+ Depends(...) / Required(...) capabilities
+ response model
= executable endpoint

function body
= raise NotImplementedError
```

Summonpot inspects the declaration and never calls the decorated function body. Deterministic business logic lives inside the exact application-owned capabilities, not inside a hidden handler.

> **Current status:** Pydantic contracts, provider-neutral agent execution, closed capabilities, runtime-enforced required operations, HTTP methods, runtime limits, and redacted public errors are shipped. Typed capability bindings, automatic deterministic endpoint execution, and SQLAlchemy/SQLite capability adapters remain planned.

You define an endpoint; you do not configure an agent graph or write orchestration under the decorator. The current runtime owns validation, capability orchestration, structured output, and the bounded model loop. The planned compiler will add no-model execution without changing the endpoint declaration.

| Target endpoint outcome | Execution path |
|---|---|
| Traditional exact API behavior with one legal path | Deterministic, without an LLM *(planned compiler)* |
| Several valid declared paths require a bounded choice | Agentic, using only declared capabilities |
| No declared legal path | Typed deterministic error *(planned compiler)* |

```python
from my_service.operations import record_research, search_web
from pydantic import BaseModel, Field
from summonpot import Depends, Pot, Required


class ResearchRequest(BaseModel):
    query: str = Field(min_length=3)
    depth: int = Field(default=3, ge=1, le=5)


class ResearchResponse(BaseModel):
    summary: str
    key_findings: list[str]
    sources: list[str]


pot = Pot("my-service")


@pot.summon("/research")
def research_topic(
    request: ResearchRequest,
    sources=Depends(search_web),
    receipt=Required(record_research),
) -> ResearchResponse:
    """Research this topic thoroughly and return a sourced report."""
    raise NotImplementedError


pot.serve()
```

Call it like any API:

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "quantum computing", "depth": 5}'
```

The imported functions are real, application-owned operations: `search_web` must query the approved source service, and `record_research` must perform the actual write. Summonpot does not replace their implementations with generated behavior. It exposes only those exact operations to the endpoint agent, rejects a final response until `record_research` has completed, validates the Pydantic output locally, and never executes the decorated function body.

## Why another framework?

Many approaches to building agentic APIs ask developers to learn an agent framework first—chains, planners, memory, callbacks—and then add an HTTP server around it. That makes the application responsible for both agent orchestration and API behavior.

summonpot starts from the endpoint instead. The web framework owns routing, validation, the bounded model loop, capability enforcement, and serving. Developers declare the HTTP contract and exact application authority; they do not configure a separate agent framework.

| | Agent-first stacks | summonpot |
|---|---|---|
| Mental model | "Configure an agent" | "Define an endpoint" |
| Surface area | Chains, agents, tools, memory, callbacks | Route, types, goal, capabilities |
| API exposure | HTTP layer added around the agent | Routing and execution share one contract |
| Orchestration | Application manages the loop | Framework owns the bounded loop |
| Testing | Agent internals plus HTTP wrapper | Normal HTTP contract and capability tests |
| Onboarding | Learn the stack's agent ontology | Start from HTTP and Python signatures |

## Project status

The current foundation includes Pydantic request and response contracts, provider-neutral model selection, declarative optional and mandatory capabilities, runtime-enforced required use, HTTP/OpenAPI generation, and local output validation.

Next milestones focus on typed capability inputs, outputs, and argument sources; strict SQLAlchemy and SQLite statement capabilities; deterministic-versus-agentic execution selection; proof-backed write receipts; broader typed operation failures; and optional larger execution harnesses. See the [roadmap](ROADMAP.md) for scope and ordering.

## Target deterministic and current agentic execution

The target architecture does not introduce a second decorator or a caller-provided `action` for deterministic execution. Both executors use the same four-part declaration:

```text
request model
+ fixed endpoint goal
+ exact capabilities
+ response model
```

Summonpot's target execution compiler will choose the mode for each validated request:

| Resolved contract | Execution |
|---|---|
| One complete legal operation path | Deterministic |
| A bounded choice remains | Agentic |
| No legal path exists | Typed deterministic error |

The set of capabilities is fixed in both modes. A capability is exact application-owned code, so what it does is whatever you implemented — summonpot does not make a web search or a provider call behave deterministically. What the framework fixes is authority: agentic execution means the model chooses or orders only those declared operations, and never gains arbitrary application access.

> **Current status:** declarative capabilities and required-use enforcement are shipped. Automatic deterministic endpoint execution is a planned milestone. Today, `@pot.summon` requests still run through the provider-neutral agent runtime.

### Target deterministic example (currently model-backed)

This endpoint has one fixed result path: load the account, calculate the exact balance, and return it. Once every input and output binding is declared, the planned compiler can execute it without an LLM.

```python
from accounts.operations import calculate_balance, load_account
from pydantic import BaseModel
from summonpot import Pot, Required


class BalanceRequest(BaseModel):
    account_id: str


class BalanceResponse(BaseModel):
    account_id: str
    balance: str
    currency: str


pot = Pot("accounts")


@pot.summon("/balance")
def get_balance(
    request: BalanceRequest,
    account=Required(load_account),
    balance=Required(calculate_balance),
) -> BalanceResponse:
    """Return the exact current balance for this account."""
    raise NotImplementedError
```

```json
{
  "account_id": "acc_123"
}
```

There is no action to interpret and no valid alternative to choose. Hard rules and money calculations remain inside the declared operations.

### Agentic example

This endpoint has a fixed goal, but inventory results may leave several legal fulfilment paths. The agent may compare only the declared options and must complete the real order operation before returning success.

```python
from orders.operations import check_inventory, create_order, find_substitutes
from pydantic import BaseModel
from summonpot import Depends, Pot, Required


class OrderItem(BaseModel):
    sku: str
    quantity: int


class OrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItem]


class OrderResponse(BaseModel):
    order_id: str
    selected_items: list[OrderItem]
    status: str


pot = Pot("orders")


@pot.summon("/orders")
def fulfil_order(
    request: OrderRequest,
    inventory=Depends(check_inventory),
    substitutes=Depends(find_substitutes),
    creation=Required(create_order),
) -> OrderResponse:
    """Fulfil the order using the best valid available option."""
    raise NotImplementedError
```

```json
{
  "customer_id": "123",
  "items": [{"sku": "A", "quantity": 1}]
}
```

The endpoint declaration supplies the fixed goal: fulfil the order using the best valid option. The request supplies business data only. If inventory leaves one complete path, the planned compiler can run it deterministically. If several valid substitutions remain, the agent chooses among those bounded results. It cannot call undeclared operations or grant itself a stronger runtime.

## Restricted database operations

Database access follows the same capability rule: pass exact prepared operations, never database authority.

> **Target API — planned, not shipped yet:** the SQLAlchemy and SQLite adapters below show the intended security boundary. Final names may change during implementation.

### SQLAlchemy ORM statement

The developer prepares one exact `Select` using an ORM model. The framework binds `customer_id` from validated request data, opens the session internally, executes the statement, and validates the projected result. The agent sees `load_customer(customer_id) -> CustomerView`; it never receives the statement, ORM registry, session, or engine.

```python
from orders.database import Customer, orders_session
from pydantic import BaseModel
from sqlalchemy import bindparam, select
from summonpot import FromRequest, Pot, Required, SQLAlchemyOperation


class CustomerRequest(BaseModel):
    customer_id: str


class CustomerView(BaseModel):
    customer_id: str
    tier: str
    active: bool


customer_statement = (
    select(
        Customer.id.label("customer_id"),
        Customer.tier,
        Customer.active,
    )
    .where(Customer.id == bindparam("customer_id"))
)

load_customer = SQLAlchemyOperation(
    name="load_customer",
    statement=customer_statement,
    session_factory=orders_session,
    bind={"customer_id": FromRequest("customer_id")},
    output=CustomerView,
)

pot = Pot("customers")


@pot.summon("/customers/resolve")
def resolve_customer(
    request: CustomerRequest,
    customer=Required(load_customer),
) -> CustomerView:
    """Return the exact approved customer projection."""
    raise NotImplementedError
```

Only the predefined `SELECT` can run. The model cannot change the table, columns, predicate, join, or SQL text.

### SQLite operation

The SQLite adapter receives one fixed parameterized statement. The framework owns the connection and parameter binding; the agent cannot access a connection, cursor, or generic SQL executor.

```python
from orders.database import orders_database
from pydantic import BaseModel
from summonpot import FromRequest, Pot, Required, SQLiteOperation


class CancelRequest(BaseModel):
    order_id: str


class CancelReceipt(BaseModel):
    order_id: str
    rows_affected: int
    status: str


cancel_order = SQLiteOperation(
    name="cancel_order",
    database=orders_database,
    sql="""
        UPDATE orders
        SET status = 'cancelled'
        WHERE id = :order_id AND status = 'pending'
    """,
    bind={"order_id": FromRequest("order_id")},
    output=CancelReceipt,
    exactly_one_row=True,
)

pot = Pot("orders")


@pot.summon("/orders/cancel")
def cancel(
    request: CancelRequest,
    receipt=Required(cancel_order),
) -> CancelReceipt:
    """Cancel this order only when the declared operation permits it."""
    raise NotImplementedError
```

The endpoint can execute only that parameterized `UPDATE`. It cannot issue another query, interpolate SQL, inspect unrelated tables, or claim success without the validated receipt.

The planned adapters will enforce these boundaries outside the model:

- only developer-declared `Select`, `Insert`, `Update`, or `Delete` objects and fixed SQLite statements;
- explicit argument sources such as validated request fields or prior operation results;
- typed input, projection, and receipt validation;
- framework-owned sessions, connections, transactions, and serialization;
- affected-row, call-count, ordering, and once-only constraints;
- no raw `Session`, `Engine`, `Connection`, cursor, model registry, arbitrary SQL, shell, or filesystem access.

## Installation

```bash
pip install summonpot            # core
pip install summonpot[serve]     # + HTTP server (FastAPI/uvicorn)
pip install summonpot[cli]       # + Typer CLI
pip install summonpot[all]       # everything
```

Install the provider you want to use:

```bash
pip install "summonpot[openai]"       # OpenAI
pip install "summonpot[anthropic]"    # Anthropic
pip install "summonpot[google]"       # Google Gemini
pip install "summonpot[groq]"         # Groq
pip install "summonpot[mistral]"      # Mistral
pip install "summonpot[openrouter]"   # OpenRouter
pip install "summonpot[xai]"          # xAI
pip install "summonpot[all]"          # serving, CLI, and every provider
```

Choose a model with an explicit `provider:model` identifier and set that provider's standard API-key environment variable:

```bash
export SUMMONPOT_MODEL=anthropic:claude-sonnet-4-5
export ANTHROPIC_API_KEY='<your key>'
```

OpenRouter keeps the upstream provider and model in the portion after the first colon:

```bash
export SUMMONPOT_MODEL=openrouter:anthropic/claude-sonnet-4
export OPENROUTER_API_KEY='<your key>'
```

The endpoint API does not change between providers. Unprefixed legacy model names such as `gpt-4o-mini` continue to resolve as `openai:gpt-4o-mini`.

## Quick Start

Create a file `app.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field
from summonpot import Pot


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)
    max_topics: int = Field(default=5, ge=1, le=20)


class AnalyzeResponse(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    topics: list[str]
    explanation: str


pot = Pot("my-service")


@pot.summon("/analyze")
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze the text and return its sentiment, topics, and explanation."""
    raise NotImplementedError
```

Serve it:

```bash
summonpot serve app.py                  # serves on 0.0.0.0:8000
summonpot serve app.py --port 9000
```

Or from Python:

```python
pot.serve()                             # 0.0.0.0:8000
pot.serve(host="127.0.0.1", port=9000)
```

> **Binding and exposure:** `0.0.0.0` accepts connections on every interface. That is
> the right default for a container, but it is wider than uvicorn's own `127.0.0.1`.
> summonpot has no authentication layer yet, and every endpoint spends provider credit
> on each call, so do not expose a pot directly to untrusted callers. Put
> authentication in front of it and bound the runtime:

```python
from summonpot import Pot, UsageLimits
from summonpot.runtime import Runtime

pot = Pot("my-service", runtime=Runtime(usage_limits=UsageLimits(request_limit=8), timeout=30.0))
```

## Examples

See [`examples/`](examples/) for executable applications arranged by complexity: a minimal typed endpoint, required exact calculations, bounded agentic order fulfillment, GET and POST routing, runtime limits, and a multi-file support service with a required persisted ticket.

## The Summoning Model

| Concept | As summoning |
|---|---|
| Route definition | "At this path, I summon..." |
| Docstring | The incantation (system prompt) |
| Capabilities | Exact operations placed in the circle |
| Request model | What the summoner brings |
| Return type | What appears |

## Declarative dependencies

An endpoint signature can combine one Pydantic request model, exact deterministic dependencies, and one Pydantic response model:

```python
from my_service.operations import check_capacity, load_constraints
from pydantic import BaseModel, Field
from summonpot import Depends, Required


class PlanRequest(BaseModel):
    goal: str
    constraints: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    steps: list[str]
    risks: list[str]


@pot.summon("/plan")
def plan(
    request: PlanRequest,
    stored_constraints=Depends(load_constraints),
    capacity=Required(check_capacity),
) -> PlanResponse:
    """Create an actionable plan that respects every constraint."""
    raise NotImplementedError
```

The signature is the complete execution contract. The decorated function is declarative—the runtime does not execute its body.

- The request model alone defines and validates incoming JSON.
- The response model defines OpenAPI output and validates the final result.
- `Depends(operation)` gives the agent an exact deterministic operation it may call.
- `Required(operation)` rejects final output until the exact operation has run successfully.
- Dependencies never become HTTP request fields.
- The agent receives no undeclared application operations.
- Provider output is retried within a bounded budget when it violates the response contract or skips a required operation.

A Pydantic endpoint has exactly one request parameter plus any declarative dependencies. Put all incoming fields inside the request model so there is one clear JSON body.

## How it works

summonpot inspects your endpoint function:

- **Docstring** → becomes the fixed endpoint goal
- **Pydantic request model** → becomes the validated JSON request body and OpenAPI input schema
- **Pydantic response model** → becomes the provider's structured-output schema, runtime validator, and OpenAPI response schema
- **Dependencies** → become the endpoint's closed set of optional or mandatory deterministic capabilities

The framework owns the agent loop, capability orchestration, required-operation enforcement, and structured-output validation. The endpoint body contains no handler code.

See [Declarative capability endpoints](docs/declarative-capabilities.md) for the execution and security contract.

## Provider and model configuration

Summonpot uses provider-qualified model identifiers. Provider SDKs, authentication, tool calling, structured-output negotiation, and model-specific behavior are handled internally by the provider-agnostic runtime.

| Provider | Install extra | Model example | API-key variable |
|---|---|---|---|
| OpenAI | `summonpot[openai]` | `openai:gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `summonpot[anthropic]` | `anthropic:claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Google | `summonpot[google]` | `google:gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Groq | `summonpot[groq]` | `groq:llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Mistral | `summonpot[mistral]` | `mistral:mistral-large-latest` | `MISTRAL_API_KEY` |
| OpenRouter | `summonpot[openrouter]` | `openrouter:anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| xAI | `summonpot[xai]` | `xai:grok-4` | `XAI_API_KEY` |

To try summonpot without a provider account, use the built-in keyless model:

```bash
export SUMMONPOT_MODEL=test
```

It answers every endpoint with schema-valid placeholder data, so routing,
validation, and capability wiring can all be exercised before any key exists.

`SUMMONPOT_MODEL` sets the default for every endpoint:

```bash
export SUMMONPOT_MODEL=openrouter:anthropic/claude-sonnet-4
```

An endpoint can override it without changing its request, response, or capabilities:

```python
@pot.summon(
    "/research",
    model="anthropic:claude-sonnet-4-5",
)
def research_topic(
    request: ResearchRequest,
    sources=Depends(search_web),
    receipt=Required(record_research),
) -> ResearchResponse:
    """Research this topic."""
    raise NotImplementedError
```

## Bounding a call

Every production `@pot.summon` request currently runs through the configured model, so the runtime accepts a cap on what one request may spend and how long it may take:

```python
from summonpot import Pot, UsageLimits
from summonpot.runtime import Runtime

pot = Pot(
    "my-service",
    runtime=Runtime(
        usage_limits=UsageLimits(request_limit=8, total_tokens_limit=40_000),
        timeout=30.0,
    ),
)
```

Every endpoint on that pot is bounded by those limits. Exceeding a usage limit raises
`UsageLimitExceeded`; exceeding the timeout raises `TimeoutError`. Both default to
`None`, which leaves the provider engine's own limits in place — set them explicitly
for anything reachable from outside your network.

The timeout bounds how long summonpot *waits*. It cannot terminate a synchronous
capability already running in a worker thread, so a write started before the deadline
still completes after the caller sees `TimeoutError`. Give any capability that must
not outlive its request an internal deadline of its own.

Pydantic AI is an internal runtime dependency. Summonpot users do not construct Pydantic AI agents or provider clients; the stable public contract remains `Pot`, `@pot.summon`, declarative capabilities, and Pydantic endpoint models.

## Agent skills

summonpot's endpoint contract is unusual enough that a coding agent will get it wrong
unless it is told: the signature *is* the contract, and the function body is never
executed. Install the skill so your agent knows the rules before it writes an endpoint:

```bash
summonpot add skills
```

With no arguments it installs for every agent already configured in the project.
Choose one explicitly with `--agent`:

```bash
summonpot add skills --agent claude      # .claude/skills/summonpot/SKILL.md
summonpot add skills --agent cursor      # .cursor/rules/summonpot.mdc
summonpot add skills --agent windsurf    # .windsurf/rules/summonpot.md
summonpot add skills --agent copilot     # .github/copilot-instructions.md
summonpot add skills --agent cline       # .clinerules/summonpot.md
summonpot add skills --agent codex       # AGENTS.md
```

```bash
summonpot add skills --path ./myproject/
```

Files the project also owns — `AGENTS.md` and `.github/copilot-instructions.md` — are
edited in place inside a managed block, so your own instructions are preserved and a
reinstall replaces the block rather than appending another copy.

The skill covers the endpoint contract, what not to write, every rule enforced at
registration, HTTP methods and query parameters, bounding a call, and what each failure
status means.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/tugrulguner/summonpot.git
cd summonpot
uv sync --all-extras
```

```bash
make check    # lint + typecheck + test
make lint     # ruff check + format check
make test     # pytest
make format   # auto-format
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull-request and single-source release instructions.

## License

MIT
