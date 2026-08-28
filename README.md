# summonpot

<p align="center">
  <strong>One endpoint declaration for deterministic operations and agentic decisions.</strong>
</p>

<p align="center">
  Summonpot is a contract-first Python framework for turning typed endpoint declarations
  into executable APIs. The same declaration defines the request, fixed goal, exact
  application operations, model-owned choices, response, HTTP route, and OpenAPI contract.
  Deterministic application code and model-driven decisions share one framework instead of
  becoming separate handlers, agent graphs, and integration layers.
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
  <a href="#what-ships-today">What ships</a> ·
  <a href="#examples">Examples</a> ·
  <a href="#contributing">Contributing</a>
</p>

The declaration says which parts of a flow are deterministic and where the model may
choose:

- `FromRequest("customer_id")` removes `customer_id` from the operation tool schema and
  injects the validated value deterministically.
- `AgentChoice()` leaves only `format` to the model.
- `Exactly(1)` permits one operation start and requires one locally validated success.
- `CustomerView` validates the result before it becomes an HTTP response.

On current `main`, every `@summon(...)` request still uses the configured model runtime.
The supported bound shape keeps trusted operation arguments and validation under framework
control while the model handles the declared semantic choice. Request values still appear
in the model's user message; tool-schema hiding is not prompt secrecy. Automatic no-model
execution for fully resolved declarations remains planned, and published 0.6.0 predates
the bound runtime shown here.

<p align="center">
  <img src="https://raw.githubusercontent.com/tugrulguner/summonpot/014814f7b304da5309afb43d22446bd6dda15c7d/docs/assets/authority-boundary.svg" alt="A validated request value and model-supplied tool argument flow through one start-bounded Summonpot operation into a validated response" width="960">
</p>

## Quick start

### 1. Install

The bound-operation runtime shown below is on current `main` and is awaiting its next
package release. Until then, install the merge commit that introduced it:

```bash
pip install "summonpot[serve,cli] @ git+https://github.com/tugrulguner/summonpot.git@4819a8bc0503b3d4f3995fd76a6f678abd07047d"
export SUMMONPOT_MODEL=test
```

The built-in test model is keyless, but it is not a dry-run sandbox. It may execute attached
operations with generated arguments. Use harmless operations while testing wiring.

### 2. Create `app.py`

```python
from typing import Literal

from pydantic import BaseModel
from summonpot import (
    AgentChoice,
    Exactly,
    FromRequest,
    Operation,
    Required,
    Summon,
)


class CustomerRequest(BaseModel):
    customer_id: str


class CustomerView(BaseModel):
    display: str


_CUSTOMERS = {"customer-7": "Ada"}


def load_customer(
    customer_id: str,
    format: Literal["summary", "detailed"],
) -> str:
    """Load one approved customer record in the selected display format."""
    return f"{format}: {_CUSTOMERS[customer_id]}"


customer_lookup = Operation(
    load_customer,
    bind={
        "customer_id": FromRequest("customer_id"),
        "format": AgentChoice(),
    },
    output=str,
)

summon = Summon("customer-api")


@summon("/customers/view")
def customer_view(
    request: CustomerRequest,
    customer=Required(customer_lookup, calls=Exactly(1)),
) -> CustomerView:
    """Load the requested customer once and return a concise approved view."""
    ...
```

### 3. Serve and call it

```bash
summonpot serve app.py --host 127.0.0.1 --port 8000
```

Open [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs), or call the route:

```bash
curl -X POST http://127.0.0.1:8000/customers/view \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":"customer-7"}'
```

The test model returns a schema-valid `CustomerView`; its placeholder text may vary. A larger
related version of this pattern is
[`examples/07_bound_operation.py`](examples/07_bound_operation.py). Provider installation
and model selection are covered in [Providers](#providers).

## Why summonpot?

A conventional API framework puts deterministic orchestration in a handler. An agent-first
stack starts from a model workflow and adds HTTP around it. Summonpot starts from one
endpoint contract that can contain both exact application operations and explicit
model-driven choices:

```text
request model
+ fixed goal in the docstring
+ exact Depends(...) / Required(...) operations
+ argument ownership
+ response model
= executable HTTP endpoint
```

| | Conventional API | Agent-first stack | Summonpot |
|---|---|---|---|
| Starting point | Write a handler | Configure an agent | Declare an endpoint contract |
| Deterministic work | Handler orchestration | Exposed as tools | Exact declared operations |
| Agentic decisions | Added as a separate model workflow | Primary abstraction | Declared model choices; `AgentChoice` in the supported bound shape |
| HTTP contract | Defined around the handler | Added around the agent | Generated from the declaration |
| Authority | Held by application code | Assembled from tools and runtime context | Closed operation set; bindings enforced in the supported shape |
| Final output | Handler convention | Provider or framework convention | Locally validated response model |

Applications keep one public API as the balance changes between deterministic execution and
model choice. The model remains useful where semantic judgment is required, while exact
operations retain application-owned behavior and authorization. It does not receive a raw
database session, unrestricted application container, shell, or filesystem merely because
the endpoint needs one exact operation.

## What ships today

This inventory describes current `main`; published 0.6.0 predates the bound-operation
runtime called out below.

- Typed request and response contracts with generated HTTP routes and OpenAPI.
- A fixed endpoint goal taken from the declaration docstring.
- One declaration model for deterministic application operations and agentic decisions.
- Closed sets of application-owned operations through `Depends(...)` and `Required(...)`.
- Per-request enforcement that rejects final output until every required operation succeeds.
- One complete bound-operation slice with trusted `FromRequest` injection, direct
  `AgentChoice`, hidden callable defaults, `Exactly(1)` start accounting, and local
  operation-output validation.
- Registration-time validation for typed operation bindings and known incompatibilities.
- Provider-neutral model selection, bounded retries, usage limits, timeouts, and redacted
  public failures.
- GET, POST, PUT, PATCH, DELETE, and HEAD routes keyed by `(path, method)`.
- A keyless test model and installable coding-agent guidance.

Broader bound multi-operation execution, `FromResult`, runtime `FromContext`, `after` ordering,
broader call bounds, automatic no-model execution, database adapters, streaming, and
built-in authentication remain planned. See [ROADMAP.md](ROADMAP.md) for their order and
security constraints.

## How deterministic operations and agentic decisions share one declaration today

The same endpoint binds trusted data to an exact application operation and reserves only
the semantic choice for the model. The enforced flow below currently applies to one
required typed operation with `Exactly(1)`, `output=`, no `after`, and bindings limited to
`FromRequest`, direct `AgentChoice`, or callable defaults. Other operation shapes continue
to expose their callable arguments to the model.

```text
HTTP request
    |
    v
Request validation and OpenAPI contract
    |
    v
Compiled endpoint authority
    |-- inject trusted request values
    |-- expose only model-owned arguments
    |-- reserve permitted operation starts
    |-- validate operation results
    v
Configured provider-neutral model
    |-- may call only declared operations
    v
Required-operation gate
    |
    v
Local response validation
    |
    v
HTTP response
```

Pydantic AI is an internal runtime dependency. Applications use `Summon`, `@summon`,
Pydantic models, and declared operations; they do not construct provider clients or
Pydantic AI agents.

## Capability contracts

A bare callable remains the smallest capability:

```python
def calculate_quote(
    unit_price_cents: int,
    quantity: int,
    tax_rate_percent: str,
) -> dict[str, int]:
    """Calculate a quote using the service's approved pricing rules."""
    return pricing_service.calculate(
        unit_price_cents=unit_price_cents,
        quantity=quantity,
        tax_rate_percent=tax_rate_percent,
    )
```

Attach it to exactly the endpoint that may use it:

```python
from summonpot import Required


@summon("/quotes")
def create_quote(
    request: QuoteRequest,
    calculation=Required(calculate_quote),
) -> QuoteResponse:
    """Calculate and return the exact approved quote."""
    ...
```

| Declaration | Runtime contract |
|---|---|
| `Depends(operation)` | The operation is available and may be called. |
| `Required(operation)` | Final output is rejected until the operation succeeds. |
| `Required(operation, calls=Exactly(1))` with the supported bound shape | One start is permitted and one locally validated success is required. |

For bare callables and unsupported graph shapes, `Required(...)` proves successful use at
least once. Ordering, idempotency, and provenance-backed final claims are separate
contracts. Every operation must still enforce its own application authorization.

### Registration catches invalid contracts before serving

An `Operation` may declare sources such as `FromRequest`, `FromResult`, `FromContext`, or
`AgentChoice`. Summonpot verifies at registration that required arguments have sources,
references name declared values, supported choices have usable shapes, and known source
and destination types are compatible.

The checker rejects only provable incompatibility. Missing annotations, `Any`, framework
context, and relationships it cannot establish remain unknown rather than becoming false
registration errors. Runtime injection currently covers only the bound-operation shape
shown in the quick start.

## HTTP methods and OpenAPI

`POST` is the default. Body endpoints take one Pydantic request model. Bodyless methods
such as `GET`, `DELETE`, and `HEAD` declare scalar or scalar-sequence query parameters:

```python
from typing import Literal

from pydantic import BaseModel


class TicketPage(BaseModel):
    tickets: list[str]


@summon("/tickets", method="GET")
def list_tickets(
    status: Literal["open", "closed"] = "open",
    ids: list[int] | None = None,
) -> TicketPage:
    """List tickets matching the requested filters."""
    ...
```

`GET /tickets` and `POST /tickets` may coexist. Registering the same normalized
`(path, method)` twice fails at import time. Capability dependencies never become request
fields or OpenAPI parameters.

## Providers

| Provider | Install extra | Model example | API-key variable |
|---|---|---|---|
| OpenAI | `summonpot[openai]` | `openai:gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `summonpot[anthropic]` | `anthropic:claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Google | `summonpot[google]` | `google:gemini-2.5-flash` | `GOOGLE_API_KEY` |
| Groq | `summonpot[groq]` | `groq:llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Mistral | `summonpot[mistral]` | `mistral:mistral-large-latest` | `MISTRAL_API_KEY` |
| OpenRouter | `summonpot[openrouter]` | `openrouter:anthropic/claude-sonnet-4` | `OPENROUTER_API_KEY` |
| xAI | `summonpot[xai]` | `xai:grok-4` | `XAI_API_KEY` |

Set the application default through `SUMMONPOT_MODEL` or in Python:

```python
summon = Summon("research-api", model="openrouter:anthropic/claude-sonnet-4")
```

An endpoint may override that model without changing its HTTP contract. OpenRouter keeps
the upstream provider and model after the first colon. Legacy unprefixed names resolve
through OpenAI for backward compatibility.

## Bounding a call

**Binding and exposure:** A reachable endpoint can spend the operator's provider credit,
so configure explicit limits and a timeout:

```python
from summonpot import Summon, UsageLimits
from summonpot.runtime import Runtime


summon = Summon(
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
| `429` | A usage limit or provider rate limit was exceeded. |
| `502` | The provider failed or the model did not satisfy the endpoint contract. |
| `504` | The endpoint exceeded its timeout. |
| `500` | Provider configuration or application capability failed. |

Provider text, model output, and capability details stay in operator logs rather than
public error bodies. A timeout cannot terminate a synchronous capability already running
in a worker thread, so irreversible operations need their own deadline and idempotency
policy.

Summonpot currently has no authentication layer. Bind local development to `127.0.0.1`.
Put authentication in front of a service before exposing it.

## Examples

The [`examples/`](examples/) directory progresses from one typed endpoint to a multi-file
service:

| Level | Example | Demonstrates |
|---|---|---|
| 1 | [`basic_app.py`](examples/basic_app.py) | Minimal typed request and response |
| 2 | [`02_required_capability.py`](examples/02_required_capability.py) | Required exact calculation |
| 3 | [`03_agentic_order.py`](examples/03_agentic_order.py) | Bounded choice plus a required write |
| 4 | [`04_http_methods.py`](examples/04_http_methods.py) | GET/POST routing and query parameters |
| 5 | [`05_bounded_runtime.py`](examples/05_bounded_runtime.py) | Limits, timeout, and model override |
| 6 | [`06_support_service/`](examples/06_support_service/) | Multi-file typed operation declarations |
| 7 | [`07_bound_operation.py`](examples/07_bound_operation.py) | Enforced trusted/model argument ownership |

The [examples guide](examples/README.md) includes an HTTP call for every level and states
which contracts execute today.

## Give your coding agent the contract

The declaration body is `...`, which a coding agent may mistake for an unfinished handler.
Install Summonpot's bundled guidance for Claude Code, Cursor, Windsurf, GitHub Copilot,
Cline, or OpenAI Codex:

```bash
summonpot add skills
```

Summonpot detects agent configuration already present in the project. Use `--agent` or
`--path` to select an agent or another project directory explicitly. Shared instruction
files are updated inside managed blocks.

## Contributing

Summonpot is early enough that a focused contribution can still shape the framework.
Useful work includes executable application examples, provider and HTTP acceptance
coverage, clearer errors, deterministic execution, typed dataflow, database operations,
and reproducible security or ergonomics reports.

For substantial contract changes, open an
[issue](https://github.com/tugrulguner/summonpot/issues/new/choose) first. Development uses
[uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/tugrulguner/summonpot.git
cd summonpot
uv sync --all-extras
make check
```

Every user-facing change needs an issue-backed or generated orphan Towncrier fragment. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Migrating from the 0.5 API

The application object is now `Summon`, the module-level variable is named `summon`, and
the application instance itself is the decorator:

```python
# 0.5
from summonpot import Pot

pot = Pot("service")


@pot.summon("/review")
def review(request: ReviewRequest) -> ReviewResponse:
    """Review this request."""
    raise NotImplementedError  # 0.5 declaration body
```

```python
# current
from summonpot import Summon

summon = Summon("service")


@summon("/review")
def review(request: ReviewRequest) -> ReviewResponse:
    """Review this request."""
    ...
```

In short: `Pot` → `Summon`, `pot` → `summon`, `@pot.summon(...)` → `@summon(...)`, and
`raise NotImplementedError` → `...`.
The CLI loads a module-level variable named `summon`. The package-root `Pot` export and the
`summonpot.pot` module have been removed, so update imports instead of relying on the old
paths. `summon.summon(...)` remains a temporary compatibility alias after constructing a
`Summon`.

## Roadmap

The public endpoint declaration is intended to stay stable as Summonpot gains selection of
the least-powerful sufficient executor:

```text
one fully resolved operation path  -> no-model deterministic executor
bounded semantic choice remains    -> model-backed agentic executor
no legal path                      -> typed deterministic error
```

The current runtime implements the model-backed path and the first enforced bound-operation
slice. Broader ordering, dataflow, deterministic execution, adapters, and operational
constraints are tracked in [ROADMAP.md](ROADMAP.md).

## Help summonpot grow

If this endpoint model is useful, [star the repository](https://github.com/tugrulguner/summonpot),
build one small endpoint, and
[report the friction](https://github.com/tugrulguner/summonpot/issues/new/choose). Real use
cases and executable examples are more valuable than speculative feature lists.

## License

[MIT](LICENSE)
