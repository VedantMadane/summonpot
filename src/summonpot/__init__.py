"""A signature-first API framework for typed endpoints and bounded agentic execution."""

from importlib.metadata import PackageNotFoundError, version

from pydantic_ai.usage import UsageLimits

from summonpot.dependencies import Depends, Required
from summonpot.pot import Pot

try:
    __version__ = version("summonpot")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["Depends", "Pot", "Required", "UsageLimits"]
