# AGENTS.md

Working notes for anyone — human or agent — changing summonpot.

For *using* summonpot, run `summonpot add skills`; that installs the endpoint contract
as a skill. This file is about developing the framework itself.

## What summonpot is

A contract-first API framework. An endpoint declaration is the executable contract:

```text
request model + docstring goal + declared capabilities + response model
```

The decorated function body is never executed. Today every request runs through the
provider-neutral agent runtime; the target is a compiler that picks the least-powerful
sufficient executor, skipping the model entirely when one legal path remains.

Two invariants govern almost every design argument:

1. **The signature is the whole contract.** Anything that pushes configuration into the
   endpoint signature is moving in the wrong direction.
2. **No executor may add capabilities, weaken validation, or change the response
   contract.**

## Layout

```text
src/summonpot/
  pot.py            @pot.summon, registration and all registration-time guards
  runtime.py        the agent loop, model resolution, usage limits and timeout
  server.py         FastAPI route construction, request schemas, HTTP error mapping
  models.py         EndpointDef, ToolDef, ParamDef
  dependencies.py   Depends / Required
  tools.py          capability construction from callables
  _annotations.py   shared annotation resolution (used by pot.py and tools.py)
  cli.py            the summonpot command
  commands/         CLI subcommands
  skills/           the shipped agent skill, and per-agent formatting
  templates/skills/ the skill body itself
```

## Rules that come from real bugs

Every rule below cost a bug. They are not style preferences.

**Never widen an `except`.** A bare `except Exception` around annotation resolution
silently degraded typed endpoints to untyped ones for months. Catch the exact error you
can handle, and let the rest surface.

**Fail at registration, not at request time.** Roughly ten of 0.3.0's changes turned
silently-wrong declarations into errors raised when the pot is imported. A wrong
declaration should never reach traffic. When adding a rule, add it to `summon()`.

**Do not use a name as a proxy for a property.** Rejecting a capability because its
first parameter is called `self` both rejected valid functions and accepted real
unbound methods with a differently-named receiver. Detect the actual property —
`__qualname__` and the owning class, in that case.

**Do not round-trip a type through a string.** `ParamDef.type_annotation` is a display
string and cannot express `int | None` or `list[int]`. Request schemas are built from
the resolved annotation object; anything that parses a type back out of text is a bug
waiting to happen.

**Respect PEP 563.** This codebase uses `from __future__ import annotations`, so
annotations are strings at runtime and a quoted annotation nests. Two consequences that
have each bitten:

- Resolving once is not enough — `"Request"` evaluates to the *string* `Request`.
- `exec` inherits the future flag from the calling module, so a test that means to
  exclude postponed annotations must `compile(..., dont_inherit=True)`. Without it the
  test asserts the opposite of its name and still passes.

**Preserve `Annotated` metadata.** `typing.get_type_hints` defaults to
`include_extras=False`, and a `Query()` in the default position replaces the
`FieldInfo` an annotation already carried. Both silently drop the user's validation
constraints.

**Never put internal detail in a response body.** Model output and provider text can
carry request data. Failures return a fixed public message; the detail goes to the
`summonpot.server` logger.

**Synchronous capabilities run in a worker thread.** They must not capture a
thread-affine resource — a default SQLite connection is the usual trap. This is also
the one breaking change in 0.3.0 that surfaces under traffic rather than at import.

**`functools.wraps` is not enough to describe a capability.** It produces a usable
schema only for a plain function; for a partial or a callable instance it leaves the
provider reading the wrapper's own annotations against the wrong module. Describe the
capability explicitly.

## Reviewing a change

In rough order of what has actually gone wrong here:

- **Does a doc claim something the code does not do?** This project has shipped several
  of these — `stream=True`, "deterministic capabilities", a `method=` that was
  discarded. A claim is a defect.
- **Does a new guard reject valid code?** Every guard added in 0.3.0 needed a
  false-positive test as well as a true-positive one. Two shipped rejecting valid input
  and were caught in review, not by tests.
- **Is the failure at the right time?** Registration beats request time; request time
  beats silence.
- **Does the test fail without the fix?** Assert it. Several tests here have passed for
  the wrong reason — one asserted `"FTER" not in text`, which is also true of `"AFTER"`.
- **Does the response leak anything?** See the rule above.

## Workflow

```bash
uv sync --all-extras          # setup
make check                    # lint, format, typecheck, tests
make format                   # before committing
```

Every user-facing change needs a towncrier fragment named for its PR:

```text
changelog.d/<pr-number>.<added|changed|deprecated|removed|fixed>.md
```

Dependabot is exempt, by label. Anything else without a fragment fails a required check
unless it carries `skip-changelog`.

Two things `make check` will not catch:

- **Workflow YAML.** A `: ` inside an unquoted scalar breaks a workflow and nothing in
  the test suite notices. Parse the file after editing it.
- **Deleted tests.** A green suite says nothing about tests that no longer exist. After
  any conflict resolution, diff the test-function inventory against the parent branch.

## Stacked pull requests

Long chains are normal here. Two things to know:

- **Squash-merging a parent orphans its children.** The child still carries the
  parent's original commits, which no longer match the squashed one. Fix by replaying
  only the child's own commits: `git rebase --onto origin/main <old-parent-tip> <branch>`.
  Prefer merge commits for chains.
- **Do not resolve conflicts by keeping both sides mechanically.** It works for imports
  and pure appends, and silently splices function bodies together everywhere else.

## Keeping the docs honest

`README.md`, `ROADMAP.md`, `docs/`, and the shipped skill in
`src/summonpot/templates/skills/` all describe behaviour. When behaviour changes, they
change in the same pull request.

The skill is enforced: `tests/test_skills_content.py` pins the rules it must keep
documenting, so a framework change that contradicts it fails the suite. Shipped
documentation that can go stale silently is worse than none.
