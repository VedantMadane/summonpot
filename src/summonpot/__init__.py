"""summonpot — Summon an agent behind any endpoint."""

from importlib.metadata import PackageNotFoundError, version

from summonpot.pot import Pot

try:
    __version__ = version("summonpot")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = ["Pot"]
