# summonpot

<p align="center">
  <img src="summonpot.png" alt="Summonpot" width="600">
</p>

<p align="center">
  <strong>Declare the contract. Bound the authority. Serve the endpoint.</strong>
</p>

<p align="center">
  A contract-first Python framework for turning typed endpoint declarations into executable APIs.
</p>

<p align="center">
  <a href="https://github.com/tugrulguner/summonpot/actions/workflows/ci.yml"><img src="https://github.com/tugrulguner/summonpot/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/summonpot/"><img src="https://img.shields.io/pypi/v/summonpot" alt="PyPI version"></a>
  <a href="https://pypi.org/project/summonpot/"><img src="https://img.shields.io/pypi/pyversions/summonpot" alt="Python versions"></a>
  <a href="https://github.com/tugrulguner/summonpot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
  <a href="https://github.com/tugrulguner/summonpot"><img src="https://img.shields.io/github/stars/tugrulguner/summonpot?style=social" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#why-summonpot">Why summonpot</a> ·
  <a href="#exact-capabilities-not-ambient-authority">Capabilities</a> ·
  <a href="#how-it-works-today">How it works</a> ·
  <a href="#examples">Examples</a> ·
  <a href="#contributing">Contributing</a>
</p>

Summonpot turns four declarations into a live HTTP endpoint:

```text
Pydantic request model
+ fixed goal in the docstring
+ exact Depends(...) / Required(...) capabilities
+ Pydantic response model
= executable endpoint

function body
= raise NotImplementedError
```

The signature is the execution contract. There is no handler body to implement, agent
graph to configure, or caller-provided `action` to interpret. Summonpot owns routing,
validation, the bounded model loop, capability enforcement, structured output, and
OpenAPI generation.

> [!IMPORTANT]
> Every current production `@pot.summon` request runs through the configured model.
> Automatic no-model execution for contracts with one fully resolved operation path is
> on the [roadmap](ROADMAP.md), not shipped behavior.

## Why summonpot?

A conventional API asks you to write a handler. An agent-first stack asks you to
configure an agent and then wrap it in HTTP. Summonpot starts from the endpoint contract
instead:

```python
@pot.summon("/research")
def research(
    request: ResearchRequest,
    sources=Depends(search_web),
    receipt=Required(save_report),
) -> ResearchResponse:
    """Research the topic and return a sourced report."""
    raise NotImplementedError
```

That declaration answers the questions an API framework needs to answer:

| Question | Declared by |
|---|---|
| What may the caller send? | `ResearchRequest` |
| What must the endpoint achieve? | The docstring |
| What application authority may execution use? | `Depends(...)` and `Required(...)` |
| What may the endpoint return? | `ResearchResponse` |
| Where is orchestration code? | Owned by summonpot |

The request carries business data only. The endpoint goal is fixed in code. The model
can call only the application operations attached to that endpoint, and a response is
not accepted until every `Required(...)` operation has completed successfully.

| | Agent-first stacks | summonpot |
|---|---|---|
| Mental model | Configure an agent | Define an endpoint |
| Public surface | Agents, chains, graphs, memory, callbacks | Route, types, goal, capabilities |
| HTTP | Added around the agent | Generated from the same contract |
| Application authority | Often assembled separately from the route | Closed by the route declaration |
| Final output | Provider or framework convention | Locally validated response model |
| Orchestration | Application-managed | Framework-managed bounded loop |

## What ships today

- **Contract-first endpoints** with a required goal and typed request/response contracts.
- **Closed capability sets** made from exact application-owned callables.
- **Optional and mandatory operations** through `Depends(...)` and `Required(...)`.
- **Runtime-enforced required use**, tracked per request rather than trusted to a prompt.
- **Typed `Operation` contracts** that declare request, prior-result, context, or
  model-chosen argument sources without expanding the endpoint API.
- **Registration-time contract validation** that rejects missing sources, invalid result
  references, unsupported choices, and provably incompatible types before serving.
- **Provider-neutral model selection** for OpenAI, Anthropic, Google, Groq, Mistral,
  OpenRouter, and xAI.
- **Generated HTTP and OpenAPI contracts** for body and query endpoints.
- **GET, POST, PUT, PATCH, DELETE, and HEAD routes**, keyed by `(path, method)`.
- **Local response validation**, bounded retries, usage limits, timeouts, and redacted
  public failures.
- **A keyless test model** for exercising routes and schemas before adding provider
  credentials.
- **Coding-agent skills** for Claude Code, Cursor, Windsurf, GitHub Copilot, Cline, and
  OpenAI Codex.

## Quick start

### 1. Install

```bash
pip install "summonpot[serve,cli]"
```

Start without a provider account by selecting the built-in test model:

```bash
export SUMMONPOT_MODEL=test
```

The test model is keyless, not side-effect-free. An endpoint with capabilities may call
them using generated placeholder arguments. Use harmless capabilities when testing
wiring; do not attach destructive operations or treat the model as a dry-run sandbox.

### 2. Declare an endpoint

Create `app.py`:

```python
from typing import Literal

from pydantic import BaseModel, Field
from summonpot import Pot


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class ReviewResponse(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    summary: str


pot = Pot("review-api")


@pot.summon("/review")
def review(request: ReviewRequest) -> ReviewResponse:
    """Classify the text's sentiment and summarize it in one short sentence."""
    raise NotImplementedError
```

The function body is intentionally empty. Summonpot never calls it.

### 3. Serve it

```bash
summonpot serve app.py --host 127.0.0.1 --port 8000
```

Open the generated API documentation at
[`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs), or call the endpoint directly:

```bash
curl -X POST http://127.0.0.1:8000/review \
  -H 'Content-Type: application/json' \
  -d '{"text":"The endpoint contract is surprisingly small."}'
```

The test model returns schema-valid placeholder data. To receive a real model-generated
answer, install a provider extra and select a provider-qualified model:

```bash
pip install "summonpot[serve,cli,anthropic]"
export SUMMONPOT_MODEL=anthropic:claude-sonnet-4-5
export ANTHROPIC_API_KEY='<your key>'
```

The endpoint code and HTTP contract do not change when the provider changes.

## Exact capabilities, not ambient authority

A capability is ordinary application code. It runs for real; summonpot never replaces
its implementation.

```python
def calculate_quote(
    unit_price_cents: int,
    quantity: int,
    tax_rate_percent: str,
) -> dict[str, int]:
    """Calculate an exact quote using the service's approved pricing rules."""
    return pricing_service.calculate(
        unit_price_cents=unit_price_cents,
        quantity=quantity,
        tax_rate_percent=tax_rate_percent,
    )
```

Attach it to one endpoint:

```python
from summonpot import Required


@pot.summon("/quotes")
def create_quote(
    request: QuoteRequest,
    calculation=Required(calculate_quote),
) -> QuoteResponse:
    """Calculate and return the exact approved quote."""
    raise NotImplementedError
```

| Declaration | Runtime contract |
|---|---|
| `Depends(operation)` | The operation is available to the endpoint and may be called. |
| `Required(operation)` | Final output is rejected until the operation succeeds. |

`Required(...)` proves that the operation returned successfully at least once during
that request. It does not prove correct arguments, exactly-once execution, ordering,
idempotency, or that every final claim matches the operation result.

Capabilities do not become request-body fields or OpenAPI parameters. Their docstrings
and annotations define the tool schema visible to the model, while their implementations
define the real application behavior.

The capability set is closed. Typed `Operation.bind` declarations can now state and
validate where inputs are intended to come from, but the current runtime does not inject
those bound values yet; capability inputs remain model-selected during execution. Treat
them like input from an untrusted caller: validate arguments and enforce authorization
inside each operation. Pass exact operations, never raw database sessions, engines,
connections, cursors, arbitrary SQL, shell access, or ambient filesystem authority.

See the complete executable
[`Required(...)` quote example](examples/02_required_capability.py).

## Typed operation contracts fail before serving

Use `Operation` when a capability's dataflow is part of the endpoint contract rather
than something the model should invent:

```python
from my_service.models import Customer, CustomerRequest, CustomerResponse
from my_service.operations import load_customer
from summonpot import FromRequest, Operation, Pot, Required


pot = Pot("customer-api")

customer_from_request = Operation(
    load_customer,
    bind={"customer_id": FromRequest("customer_id")},
    output=Customer,
)


@pot.summon("/customers")
def get_customer(
    request: CustomerRequest,
    customer=Required(customer_from_request),
) -> CustomerResponse:
    """Load this customer and return the approved customer view."""
    raise NotImplementedError
```

The contract is immutable after construction. At registration, summonpot verifies that:

- every required operation argument has an explicit source;
- `FromRequest(...)` names a real request field;
- `FromResult(...)` names a declared producer and a readable, typed output field;
- `AgentChoice(...)` selects from a supported collection and fits its receiving argument;
- known source, element, and destination types are compatible; and
- ordering references name operations declared by the same endpoint.

The rule is deliberately conservative: a declaration is rejected only when its
incompatibility is provable. Missing annotations, `Any`, framework context, and type
relationships the checker cannot establish remain unknown rather than becoming false
registration errors. An annotation that names a type Python cannot resolve is still an
invalid endpoint declaration and fails at import.

For example, binding an `int` request field to a `str` operation argument fails while the
module is imported. A `Customer` value may feed a `Person` argument when `Customer` is a
subclass, and Python's numeric widening permits `int` or `bool` to feed `float`.

> [!IMPORTANT]
> Registration validates and stores `FromRequest`, `FromResult`, `FromContext`,
> `AgentChoice`, and `after` declarations today. Runtime binding injection, ordering
> execution, and automatic no-model paths remain planned. Until those layers ship, the
> model-backed runtime still supplies capability arguments.

## How it works today

```text
HTTP request
    |
    v
Pydantic request validation + OpenAPI contract
    |
    v
Runtime.call(...)
    |
    v
Configured provider-neutral model
    |
    +---- may call only declared capabilities
    |          |
    |          +---- successful Required(...) calls recorded per request
    |
    v
Required-operation gate
    |
    v
Local Pydantic response validation
    |
    v
HTTP response
```

The endpoint docstring becomes the fixed goal. Request data becomes the user message.
Capabilities become the complete set of callable operations. The response model becomes
both the structured-output schema and the final local validator.

Pydantic AI is an internal runtime dependency. Applications use `Pot`, `@pot.summon`,
Pydantic models, and declarative capabilities; they do not construct provider clients or
Pydantic AI agents.

### The contract stays stable as execution evolves

The roadmap adds a no-model executor without adding a second endpoint API:

| Contract state | Target execution |
|---|---|
| One complete operation path with every binding resolved | Execute directly without a model |
| A bounded semantic choice remains | Use the agent runtime with declared capabilities |
| No legal path exists | Return a typed deterministic error |

This compiler, runtime binding injection and ordering, SQLAlchemy/SQLite operation
adapters, write receipts, streaming, and built-in authentication are **planned, not
shipped**. See
[ROADMAP.md](ROADMAP.md) for the design boundaries and implementation order.

## HTTP methods and OpenAPI

`POST` is the default. Body endpoints take one Pydantic request model. Bodyless methods
such as `GET`, `DELETE`, and `HEAD` declare scalar or scalar-sequence query parameters:

```python
from typing import Literal

from pydantic import BaseModel


class TicketPage(BaseModel):
    tickets: list[str]


@pot.summon("/tickets", method="GET")
def list_tickets(
    status: Literal["open", "closed"] = "open",
    ids: list[int] | None = None,
) -> TicketPage:
    """List tickets matching the requested filters."""
    raise NotImplementedError
```

`GET /tickets` and `POST /tickets` may coexist. Registering the same normalized
`(path, method)` twice fails at import time, as do missing docstrings, unresolved type
annotations, invalid capability callables, duplicate capability names, unsupported query
types, and `stream=True`.

## Provider and model configuration

| Provider | Install extra | Model example | API-key variable |
|---|---|---|---|
| OpenAI | `summonpot[openai]` | `openai:gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `summonpot[anthropic]` | `anthropic:claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Google | `summonpot[google]` | `google:gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Groq | `summonpot[groq]` | `groq:llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Mistral | `summonpot[mistral]` | `mistral:mistral-large-latest` | `MISTRAL_API_KEY` |
| OpenRouter | `summonpot[openrouter]` | `openrouter:anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| xAI | `summonpot[xai]` | `xai:grok-4` | `XAI_API_KEY` |

Set one default for the pot through `SUMMONPOT_MODEL` or in Python:

```python
pot = Pot("research-api", model="openrouter:anthropic/claude-sonnet-4")
```

Override it for one endpoint without changing that endpoint's HTTP contract:

```python
@pot.summon("/research", model="anthropic:claude-sonnet-4-5")
def research(request: ResearchRequest) -> ResearchResponse:
    """Research the topic and return a sourced report."""
    raise NotImplementedError
```

OpenRouter keeps the upstream provider and model after the first colon. Legacy
unprefixed model names resolve through OpenAI for backward compatibility.

## Bounding a call

**Binding and exposure:** A reachable endpoint can spend the operator's provider credit,
so set explicit usage limits and a timeout:

```python
from summonpot import Pot, UsageLimits
from summonpot.runtime import Runtime


pot = Pot(
    "my-service",
    runtime=Runtime(
        usage_limits=UsageLimits(
            request_limit=8,
            total_tokens_limit=40_000,
        ),
        timeout=30.0,
    ),
)
```

| HTTP status | Public meaning |
|---|---|
| `422` | Request validation failed. |
| `429` | The configured usage limit or provider rate limit was exceeded. |
| `502` | The provider failed or the model did not satisfy the endpoint contract. |
| `504` | The endpoint exceeded its timeout. |
| `500` | Provider configuration or application capability failed. |

Provider text, model output, and capability details stay in operator logs rather than
public error bodies.

The timeout bounds how long summonpot waits. It cannot terminate a synchronous capability
already running in a worker thread, so give irreversible or long-running operations an
internal deadline and idempotency policy of their own. Open thread-affine resources such
as default SQLite connections inside the capability call rather than capturing them
outside it.

Summonpot currently has no authentication layer. Bind local development to `127.0.0.1`.
Before exposing a service, put authentication in front of it and configure runtime limits.

## Examples

The [`examples/`](examples/) directory grows from one endpoint to a multi-file service:

| Level | Example | What it demonstrates |
|---|---|---|
| 1 | [`basic_app.py`](examples/basic_app.py) | Minimal typed request and response |
| 2 | [`02_required_capability.py`](examples/02_required_capability.py) | Required exact calculation |
| 3 | [`03_agentic_order.py`](examples/03_agentic_order.py) | Bounded choice plus a required write |
| 4 | [`04_http_methods.py`](examples/04_http_methods.py) | GET/POST routing and query parameters |
| 5 | [`05_bounded_runtime.py`](examples/05_bounded_runtime.py) | Limits, timeout, and model override |
| 6 | [`06_support_service/`](examples/06_support_service/) | Multi-file operations and persisted ticket |

The [examples guide](examples/README.md) includes a real HTTP call for every level and
explains what runs today and what remains planned.

## Give your coding agent the contract

Summonpot's function body is declarative, which is easy for a coding agent to mistake for
a normal handler. Install the bundled skill so the agent knows the endpoint shape,
registration rules, capability boundary, HTTP behavior, and runtime caveats:

```bash
summonpot add skills
```

With no arguments, summonpot detects agent configuration already present in the project.
Choose one explicitly when needed:

```bash
summonpot add skills --agent claude
summonpot add skills --agent cursor
summonpot add skills --agent windsurf
summonpot add skills --agent copilot
summonpot add skills --agent cline
summonpot add skills --agent codex
```

Use `--path ./myproject` to target another project directory. Shared files such as
`AGENTS.md` and `.github/copilot-instructions.md` are updated inside a managed block so
surrounding project instructions remain intact.

## Contributing

Summonpot is early enough that a focused contribution can still shape the framework, not
just polish its edges.

Useful places to contribute include:

- executable examples for real application workflows;
- provider and HTTP acceptance coverage;
- clearer errors, safer defaults, and API ergonomics;
- typed capability contracts and result validation;
- exact database-operation adapters;
- the deterministic execution compiler described in the roadmap;
- documentation, diagrams, and reproducible bug reports.

For substantial behavior or architecture changes, open an
[issue](https://github.com/tugrulguner/summonpot/issues/new/choose) first so the public
contract and security boundary stay coherent.

Development uses [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/tugrulguner/summonpot.git
cd summonpot
uv sync --all-extras
make check
```

Every user-facing change needs a numbered Towncrier fragment. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Roadmap

The long-term goal is one stable endpoint declaration with the least-powerful sufficient
executor behind it:

```text
one fully resolved operation path  -> no-model deterministic executor
bounded semantic choice remains    -> model-backed agentic executor
no legal path                      -> typed deterministic error
```

The ordering, security constraints, non-goals, and shipped foundation live in
[ROADMAP.md](ROADMAP.md).

## Help summonpot grow

If the endpoint-first model is useful to you:

- [Star the repository](https://github.com/tugrulguner/summonpot) so more Python
  developers can find it.
- Build one small endpoint and
  [report the friction](https://github.com/tugrulguner/summonpot/issues/new/choose).
- Share a real use case, add an executable example, or contribute to a roadmap milestone.

Early feedback is especially valuable because the public contract is small and the next
execution layers are being designed around it now.

## License

[MIT](LICENSE)
