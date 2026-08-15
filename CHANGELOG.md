# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Unreleased changes live as fragment files in [`changelog.d/`](changelog.d/) until a
release assembles them here — run `make changelog-draft` to preview them.

<!-- towncrier release notes start -->

## [0.3.0] - 2026-08-15

### Upgrading from 0.2.0

This release turns a number of silently-wrong declarations into errors. Most surface
the moment a pot is imported, so an upgrade either starts cleanly or tells you exactly
what to change.

Registration now fails for an endpoint that:

- has no docstring — the docstring is the endpoint's goal, so it cannot be empty;
- has a path without a leading slash;
- reuses a `(path, method)` pair already registered;
- passes `stream=True`, which was never implemented;
- has an annotation that cannot be resolved, such as a `TYPE_CHECKING`-only import or
  a model defined inside a function;
- declares a capability that is an unbound method or is not callable;
- uses a bodyless method (`GET`, `DELETE`, `HEAD`) with a Pydantic request model, an
  unsupported HTTP verb, or a parameter with no query encoding such as a mapping.

Two changes alter behaviour rather than rejecting it:

- **`method=` is now honoured.** An endpoint that declared `method="GET"` previously
  served `POST`; it now serves `GET`, and its parameters move to the query string.
  Clients of such an endpoint need updating.
- **Request validation is stricter.** A generic such as `list[int]` now validates its
  element types instead of accepting anything, so requests that were wrongly accepted
  may now return 422. Optional parameters accept an explicit `null`, which they
  previously rejected.

One change surfaces under traffic rather than at import, and is the one worth checking
before deploying:

- **Synchronous capabilities now run in a worker thread** so a slow operation no longer
  blocks concurrent requests. A capability that captures a thread-affine resource — a
  default SQLite connection is the common case — will now fail at request time. Give
  such capabilities their own connection per call.

Finally, endpoint failures now return meaningful status codes (`429`, `502`, `504`)
rather than an opaque `500`, and the response body no longer carries model output or
provider text. Anything depending on the previous bodies should read the status instead.

### Added

- Add `usage_limits` and `timeout` to `Runtime`, and re-export `UsageLimits`, so a single endpoint call can be capped on requests, tokens, cost, and wall-clock time. ([#23](https://github.com/tugrulguner/summonpot/pull/23))
- Add `Pot(model=...)` and `Pot(runtime=...)`, and resolve `SUMMONPOT_MODEL` at call time so setting it after import still applies. ([#33](https://github.com/tugrulguner/summonpot/pull/33))
- Honour `method=` on `@pot.summon`, registering the declared HTTP verb and taking parameters as a query string for methods that carry no body. ([#38](https://github.com/tugrulguner/summonpot/pull/38))
- Added progressive, executable examples covering typed endpoints, required deterministic capabilities, bounded agentic choices, HTTP methods, runtime limits, provider selection, and multi-file services. ([#41](https://github.com/tugrulguner/summonpot/pull/41))

### Changed

- Move the shared annotation helpers into a single module so endpoint and capability inspection can no longer drift apart. ([#26](https://github.com/tugrulguner/summonpot/pull/26))
- Raise the CI coverage floor from 50% to 85%, close to the project's actual 88%, so a real regression fails the build. ([#34](https://github.com/tugrulguner/summonpot/pull/34))
- Document that `serve()` binds every interface by default, that endpoints carry no authentication yet, and how to bound and protect an exposed pot. ([#35](https://github.com/tugrulguner/summonpot/pull/35))
- Document that the closed capability set governs which operations run, not the arguments they receive, and that each capability must validate its own inputs. ([#36](https://github.com/tugrulguner/summonpot/pull/36))
- Reuse an endpoint's agent across requests by moving required-capability tracking onto per-run state, instead of rebuilding every tool and output schema on each call. ([#37](https://github.com/tugrulguner/summonpot/pull/37))

### Fixed

- Load pot files that define dataclasses by registering the module in `sys.modules` before executing it. ([#17](https://github.com/tugrulguner/summonpot/pull/17))
- Report an unloadable pot file once, instead of following it with the exit code formatted as a second error. ([#18](https://github.com/tugrulguner/summonpot/pull/18))
- Append the pot file's directory to `sys.path` instead of prepending it, so a neighbouring module can no longer shadow the standard library. ([#19](https://github.com/tugrulguner/summonpot/pull/19))
- Run synchronous capabilities in a worker thread so a slow operation no longer blocks concurrent requests, and await callable objects whose `__call__` is async. ([#20](https://github.com/tugrulguner/summonpot/pull/20))
- Accept `functools.partial` and callable objects as capabilities, so an operation can carry a connection or configuration, and raise a clear error for values that are not callable. ([#21](https://github.com/tugrulguner/summonpot/pull/21))
- Reject an unbound method used as a capability at registration, instead of hiding `self` from the declared parameters while still demanding it in the schema sent to the model. ([#22](https://github.com/tugrulguner/summonpot/pull/22))
- Generate request schemas from the resolved annotation, so optional parameters accept null, `Any` accepts any JSON value, and generics validate their element types. ([#24](https://github.com/tugrulguner/summonpot/pull/24))
- Return meaningful status codes when an endpoint exceeds its budget, times out, or the model fails to satisfy the contract, instead of an opaque 500. ([#25](https://github.com/tugrulguner/summonpot/pull/25))
- Raise at registration when an endpoint annotation cannot be resolved, instead of silently degrading the endpoint to an untyped request body and response. ([#27](https://github.com/tugrulguner/summonpot/pull/27))
- Reject an endpoint without a docstring at registration, instead of running it with an empty agent instruction. ([#28](https://github.com/tugrulguner/summonpot/pull/28))
- Reject an endpoint path that does not start with '/' at registration, instead of building a route no request can reach. ([#29](https://github.com/tugrulguner/summonpot/pull/29))
- Reject a second endpoint registered on an existing path, instead of silently making it unreachable while documenting it in place of the first. ([#30](https://github.com/tugrulguner/summonpot/pull/30))
- Raise when an endpoint is declared with `stream=True`, instead of accepting the flag and returning a fully buffered response. ([#31](https://github.com/tugrulguner/summonpot/pull/31))
- Copy pot-level capabilities per endpoint so marking one `Required` cannot make it required for every other endpoint that declares it. ([#32](https://github.com/tugrulguner/summonpot/pull/32))
- Allow `SUMMONPOT_MODEL=test` to use pydantic-ai's built-in keyless model, so summonpot can be tried without a provider account. ([#39](https://github.com/tugrulguner/summonpot/pull/39))
- Report a missing or invalid provider configuration as a labelled error with the cause in the server log, instead of an opaque 500. ([#40](https://github.com/tugrulguner/summonpot/pull/40))


## [0.2.0] - 2026-08-12

### Added

- Add first-class Pydantic request and response contracts with provider-neutral structured output, tool execution, HTTP validation, OpenAPI schemas, and locally validated runtime results. ([#8](https://github.com/tugrulguner/summonpot/pull/8))
- Add declarative `Depends` and runtime-enforced `Required` operations so endpoint signatures define a closed deterministic capability set without handler code or extra HTTP fields. ([#9](https://github.com/tugrulguner/summonpot/pull/9))
- Expand runtime, deterministic operation, and CLI test coverage, including mandatory capability omission and exact command-line failure diagnostics. ([#10](https://github.com/tugrulguner/summonpot/pull/10))
- Document the shipped declarative capability model and publish the roadmap for typed operations, database adapters, execution selection, receipts, stable failures, and optional larger harnesses. ([#11](https://github.com/tugrulguner/summonpot/pull/11))
- Document deterministic and agentic endpoint execution modes, decision rules, examples, and the current status of automatic execution selection. ([#13](https://github.com/tugrulguner/summonpot/pull/13))
- Lead with the signature-only, no-handler endpoint contract for unified deterministic and agentic execution, and document planned SQLAlchemy and SQLite capability adapters with restricted database-operation examples. ([#14](https://github.com/tugrulguner/summonpot/pull/14))

### Fixed

- Stop exposing summonpot's internal endpoint and runtime closure state as query parameters in generated OpenAPI schemas. ([#7](https://github.com/tugrulguner/summonpot/pull/7))
- Correct README examples and terminology to use real application-owned capabilities consistently and remove placeholder operations and unimplemented streaming claims. ([#12](https://github.com/tugrulguner/summonpot/pull/12))


## [0.1.0] - 2026-08-10

### Added

- Add continuous integration, packaging, changelog tooling, and developer Makefile targets. ([#1](https://github.com/tugrulguner/summonpot/pull/1))
- Add the initial summonpot framework with agentic API endpoints, automatic request schemas, tool calling, OpenAI-compatible model providers, CLI serving, and generated OpenAPI documentation. ([#2](https://github.com/tugrulguner/summonpot/pull/2))

### Changed

- Add comprehensive framework documentation, quick-start instructions, and usage examples. ([#3](https://github.com/tugrulguner/summonpot/pull/3))
- Add release automation, dependency updates, pull-request labeling, and stale issue management. ([#4](https://github.com/tugrulguner/summonpot/pull/4))

### Fixed

- OpenAPI metadata now derives its version from installed package metadata, keeping `pyproject.toml` as the single source updated by `uv version`. ([#5](https://github.com/tugrulguner/summonpot/pull/5))
