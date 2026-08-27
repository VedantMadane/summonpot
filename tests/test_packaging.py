"""Checks that the typed-package contract holds in the artifact, not just the tree.

`Typing :: Typed` in the metadata is a promise to type checkers, and PEP 561
says the marker file is how that promise is kept. A classifier without a
`py.typed` is a claim the installed distribution cannot back up, so both halves
are asserted together.
"""

from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path

import summonpot

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "summonpot"


def test_py_typed_marker_sits_beside_the_package_init():
    """PEP 561 requires the marker inside the import package, not the sdist root."""
    marker = PACKAGE / "py.typed"

    assert marker.is_file(), (
        f"{marker} is missing; the Typing :: Typed classifier is unbacked"
    )
    assert (marker.parent / "__init__.py").is_file(), (
        "py.typed must live next to __init__.py, or type checkers will not find it"
    )


def test_py_typed_marker_is_empty():
    """PEP 561 defines the marker by presence; content would only invite drift."""
    assert (PACKAGE / "py.typed").read_bytes() == b""


def test_py_typed_ships_with_the_importable_package():
    """Resolve through the import system, so an install that dropped it fails here.

    `files()` points at whatever `import summonpot` actually resolved to -- the
    checkout under an editable install, site-packages under a real one -- which
    is the copy a consumer's type checker will look at.
    """
    assert files(summonpot).joinpath("py.typed").is_file()


def test_typed_classifier_is_declared():
    """The other half of the contract: drop one and this test names the other."""
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = metadata["project"]["classifiers"]

    assert "Typing :: Typed" in classifiers, (
        "py.typed ships but the classifier is gone; installers no longer advertise "
        "the package as typed"
    )
