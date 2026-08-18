---
name: "review-code"
description: "Review a summonpot change for the defects this codebase actually produces: docs claiming unshipped behaviour, guards that reject valid code, failures raised too late, tests that pass for the wrong reason, and internal detail leaking into responses. Use before opening a pull request or when reviewing a diff."
---

# Reviewing a summonpot change

Check the diff against the defects this project has actually shipped, in the order
they have cost the most.

## 1. Does a doc claim something the code does not do?

The most repeated defect here. Shipped examples: `stream=True` documented as working
while nothing read the flag; `method=` accepted and discarded; "capabilities themselves
remain deterministic" claiming a guarantee the framework cannot give.

A claim is a defect. Check `README.md`, `ROADMAP.md`, `docs/`, docstrings, and
`src/summonpot/templates/skills/summonpot.md`.

```bash
grep -rn "stream\|method=" README.md docs/ src/summonpot/templates/skills/
```

## 2. Does a new guard reject valid code?

Every registration guard needs a **false-positive test**, not only a true-positive one.
Two guards shipped rejecting valid input:

- an unbound-method check that rejected any function whose first parameter was `self`;
- an annotation check that rejected `request: "Request"` where `Request` existed.

For any new rule, write the case that should still be **accepted** and run it.

## 3. Is the failure raised at the right time?

Registration beats request time; request time beats silence. A wrong declaration should
never reach traffic. New rules belong in `summon()` in `pot.py`.

## 4. Does the test fail without the fix?

Assert it directly:

```bash
git stash push -q src/ && uv run pytest tests/ -q; git stash pop -q
```

Tests here have passed for the wrong reason — one asserted `"FTER" not in text`, which
is also true of `"AFTER"`. Another used `exec` without `dont_inherit=True`, inheriting
this codebase's postponed annotations and asserting the opposite of its own name.

## 5. Does anything internal reach a response body?

Model output and provider text can carry request data. Failures return a fixed public
message; detail goes to the `summonpot.server` logger. Grep the diff for interpolated
exception text in an `HTTPException`.

## 6. Type handling

- No type round-tripped through a display string — use the resolved annotation.
- `typing.get_type_hints` called with `include_extras=True`, or `Annotated` constraints
  are dropped.
- No `Query()` in a default position on a scalar; it replaces the annotation's own
  `FieldInfo`.
- No widened `except`. Catch the exact error.

## 7. Before finishing

```bash
make check
```

Two things it will not catch:

- **Workflow YAML** — parse it if you edited one.
- **Deleted tests** — a green suite says nothing about tests that no longer exist.
  After any conflict resolution, diff the test-function inventory against the parent.
