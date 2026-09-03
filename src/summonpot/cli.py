"""summonpot CLI — serve your Summon application from the command line."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import typer

from summonpot.commands.add_skills import add_skills
from summonpot.summon import Summon


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        typer.echo(f"summonpot {version('summonpot')}")
        raise typer.Exit()


app = typer.Typer(
    name="summonpot",
    help=(
        "A contract-first Python framework for modernizing APIs for AI through exact "
        "application behavior and explicitly bounded agent-owned decisions."
    ),
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Define and serve typed endpoints with bounded agentic execution."""


add_app = typer.Typer(help="Add summonpot support to a project.", no_args_is_help=True)
app.add_typer(add_app, name="add")
add_app.command("skills")(add_skills)


@app.command("serve")
def serve_command(
    source: str = typer.Argument(
        ...,
        help="Path to a Python file containing a Summon instance named 'summon'.",
    ),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to."),
) -> None:
    """Serve a Summon application as an HTTP API."""
    summon = _load_summon(source)
    typer.echo(f"Summoning {summon.name} on http://{host}:{port}")
    summon.serve(host=host, port=port)


def _load_summon(source: str) -> Summon:
    """Load a Summon instance from a Python file."""
    filepath = Path(source).resolve()
    if not filepath.exists():
        typer.echo(f"Error: file not found: {filepath}", err=True)
        raise typer.Exit(1)

    # Appended, not prepended: the directory has to stay importable for the life of
    # the process, because capabilities may import siblings lazily while serving.
    # Prepending it would let a neighbouring types.py or json.py shadow the stdlib
    # for every later import, including uvicorn's.
    project_dir = str(filepath.parent)
    if project_dir not in sys.path:
        sys.path.append(project_dir)

    # Raised outside the try below: typer.Exit subclasses RuntimeError, so an
    # `except Exception` around this would catch it and report the exit code
    # as though it were a load error.
    spec = importlib.util.spec_from_file_location("_summonpot_user", filepath)
    if spec is None or spec.loader is None:
        typer.echo(f"Error: could not load module from {filepath}", err=True)
        raise typer.Exit(1)

    mod = importlib.util.module_from_spec(spec)
    # Register before execution: dataclasses, typing.get_type_hints, enum
    # resolution, and pickling all look the defining module up in sys.modules.
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        sys.modules.pop(spec.name, None)
        typer.echo(f"Error loading {filepath}: {e}", err=True)
        raise typer.Exit(1) from None
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise

    summon = getattr(mod, "summon", None)
    if summon is None:
        typer.echo(
            f"Error: no 'summon' variable found in {filepath}. "
            "Define a Summon instance named 'summon'.",
            err=True,
        )
        raise typer.Exit(1)
    if not isinstance(summon, Summon):
        typer.echo(
            f"Error: 'summon' in {filepath} is not a Summon instance. "
            "Define a Summon instance named 'summon'.",
            err=True,
        )
        raise typer.Exit(1)
    return summon
