"""Install the summonpot skill into AI coding agent configuration."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

import typer

from summonpot.skills.content import (
    SKILL_DESCRIPTION,
    SKILL_NAME,
    claude_skill,
    cline_rule,
    codex_instruction,
    copilot_instruction,
    cursor_rule,
    skill_body,
    windsurf_rule,
)

_MANAGED_START = "<!-- summonpot:managed:start -->"
_MANAGED_END = "<!-- summonpot:managed:end -->"


class Agent(StrEnum):
    """Coding agents summonpot can install its skill for."""

    claude = "claude"
    cursor = "cursor"
    windsurf = "windsurf"
    copilot = "copilot"
    cline = "cline"
    codex = "codex"


def _write_claude(root: Path) -> list[Path]:
    """Write a Claude Code skill to .claude/skills/<name>/SKILL.md."""
    skill_dir = root / ".claude" / "skills" / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(
        claude_skill(skill_body(), name=SKILL_NAME, description=SKILL_DESCRIPTION)
    )
    return [path]


def _write_cursor(root: Path) -> list[Path]:
    rules = root / ".cursor" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    path = rules / f"{SKILL_NAME}.mdc"
    path.write_text(cursor_rule(skill_body(), description=SKILL_DESCRIPTION))
    return [path]


def _write_windsurf(root: Path) -> list[Path]:
    rules = root / ".windsurf" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    path = rules / f"{SKILL_NAME}.md"
    path.write_text(windsurf_rule(skill_body(), description=SKILL_DESCRIPTION))
    return [path]


def _write_cline(root: Path) -> list[Path]:
    rules = root / ".clinerules"
    rules.mkdir(parents=True, exist_ok=True)
    path = rules / f"{SKILL_NAME}.md"
    path.write_text(cline_rule(skill_body()))
    return [path]


def _write_copilot(root: Path) -> list[Path]:
    path = root / ".github" / "copilot-instructions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _upsert_managed_block(path, copilot_instruction(skill_body()))
    return [path]


def _write_codex(root: Path) -> list[Path]:
    path = root / "AGENTS.md"
    _upsert_managed_block(path, codex_instruction(skill_body()))
    return [path]


def _upsert_managed_block(path: Path, content: str) -> None:
    """Write the skill into a shared file without disturbing the rest of it.

    Copilot and Codex read one file that the project also uses for its own
    instructions, so the skill is fenced in a managed block and replaced in place on
    re-run rather than appended again.
    """
    block = f"{_MANAGED_START}\n{content.rstrip()}\n{_MANAGED_END}\n"
    existing = path.read_text() if path.exists() else ""

    start = existing.find(_MANAGED_START)
    end = existing.find(_MANAGED_END)
    if start != -1 and end != -1 and end > start:
        # Resume immediately after the marker, consuming a line ending only when one
        # is actually there. Assuming a trailing newline eats the first character of
        # whatever follows the block.
        after = end + len(_MANAGED_END)
        for ending in ("\r\n", "\n"):
            if existing.startswith(ending, after):
                after += len(ending)
                break
        updated = existing[:start] + block + existing[after:]
    elif existing.strip():
        updated = existing.rstrip() + "\n\n" + block
    else:
        updated = block

    path.write_text(updated)


_WRITERS: dict[Agent, Callable[[Path], list[Path]]] = {
    Agent.claude: _write_claude,
    Agent.cursor: _write_cursor,
    Agent.windsurf: _write_windsurf,
    Agent.copilot: _write_copilot,
    Agent.cline: _write_cline,
    Agent.codex: _write_codex,
}

_MARKERS: dict[Agent, tuple[str, ...]] = {
    Agent.claude: (".claude",),
    Agent.cursor: (".cursor",),
    Agent.windsurf: (".windsurf",),
    # Not bare .github/: that exists for workflows and Dependabot in almost every
    # repository, and is no evidence that Copilot instructions are in use.
    Agent.copilot: (".github/copilot-instructions.md",),
    Agent.cline: (".clinerules",),
    Agent.codex: ("AGENTS.md",),
}


def detect_agents(root: Path) -> list[Agent]:
    """Return the agents this project already has configuration for."""
    return [
        agent
        for agent, markers in _MARKERS.items()
        if any((root / marker).exists() for marker in markers)
    ]


def add_skills(
    agent: Agent | None = typer.Option(
        None,
        "--agent",
        help="Install for one agent. Defaults to every agent already configured here.",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Project directory to install into.",
    ),
) -> None:
    """Install the summonpot skill so a coding agent knows the endpoint contract."""
    root = path.resolve()
    if not root.is_dir():
        typer.echo(f"Error: not a directory: {root}", err=True)
        raise typer.Exit(1)

    if agent is not None:
        targets = [agent]
    else:
        targets = detect_agents(root)
        if not targets:
            typer.echo(
                "No agent configuration found here. Pass --agent to choose one of: "
                + ", ".join(a.value for a in Agent),
                err=True,
            )
            raise typer.Exit(1)

    for target in targets:
        for written in _WRITERS[target](root):
            typer.echo(f"{target.value}: {written.relative_to(root)}")
