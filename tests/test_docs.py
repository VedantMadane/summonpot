"""Executable checks for the README's security guidance.

Security guidance must not point users at protection that does not exist, so the
mitigation snippet is executed rather than merely read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
ROOT = README.parent


def _snippet_after(heading: str) -> str:
    text = README.read_text()
    assert heading in text, f"README no longer contains {heading!r}"
    block = text.split(heading, 1)[1]
    match = re.search(r"```python\n(.*?)```", block, re.DOTALL)
    assert match is not None, f"no Python snippet follows {heading!r}"
    return match.group(1)


def test_binding_mitigation_snippet_runs():
    """The exposure warning tells users to bound the runtime; that must be possible."""
    namespace: dict = {}

    exec(_snippet_after("Binding and exposure"), namespace)

    pot = namespace["pot"]
    assert pot._runtime.usage_limits is not None
    assert pot._runtime.timeout is not None


def test_bounding_a_call_snippet_runs():
    namespace: dict = {}

    exec(_snippet_after("## Bounding a call"), namespace)

    pot = namespace["pot"]
    assert pot._runtime.usage_limits is not None
    assert pot._runtime.timeout == 30.0


@pytest.mark.parametrize("api", ["UsageLimits"])
def test_documented_public_names_are_importable(api):
    import summonpot

    assert hasattr(summonpot, api), f"README documents summonpot.{api}"


def test_declaration_surfaces_use_ellipsis_instead_of_not_implemented():
    surfaces = [
        README,
        ROOT / "src/summonpot/pot.py",
        ROOT / "src/summonpot/contracts.py",
        ROOT / "src/summonpot/templates/skills/summonpot.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.py")),
    ]
    stale = [
        str(path.relative_to(ROOT))
        for path in surfaces
        if re.search(
            r"^\s*raise NotImplementedError\s*$", path.read_text(), re.MULTILINE
        )
    ]

    assert stale == []
