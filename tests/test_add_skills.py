"""Tests for `summonpot add skills`."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from summonpot.cli import app
from summonpot.commands.add_skills import Agent, detect_agents

runner = CliRunner()

EXPECTED: dict[str, str] = {
    "claude": ".claude/skills/summonpot/SKILL.md",
    "cursor": ".cursor/rules/summonpot.mdc",
    "windsurf": ".windsurf/rules/summonpot.md",
    "copilot": ".github/copilot-instructions.md",
    "cline": ".clinerules/summonpot.md",
    "codex": "AGENTS.md",
}


@pytest.mark.parametrize(("agent", "relative"), sorted(EXPECTED.items()))
def test_skill_is_written_where_the_agent_reads_it(agent, relative, tmp_path: Path):
    result = runner.invoke(
        app, ["add", "skills", "--agent", agent, "--path", str(tmp_path)]
    )

    assert result.exit_code == 0
    written = tmp_path / relative
    assert written.is_file()
    assert "@pot.summon" in written.read_text()


def test_claude_skill_has_the_frontmatter_that_makes_it_discoverable(tmp_path: Path):
    """Claude Code never loads a skill file without name and description."""
    runner.invoke(app, ["add", "skills", "--agent", "claude", "--path", str(tmp_path)])

    text = (tmp_path / ".claude/skills/summonpot/SKILL.md").read_text()

    assert text.startswith("---\n")
    assert '"summonpot"' in text.split("---")[1]
    assert "description:" in text.split("---")[1]


def test_shared_files_keep_their_own_content(tmp_path: Path):
    """AGENTS.md belongs to the project; the skill is a fenced guest."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# My project\n\nExisting notes.\n")

    runner.invoke(app, ["add", "skills", "--agent", "codex", "--path", str(tmp_path)])
    text = agents.read_text()

    assert "# My project" in text
    assert "Existing notes." in text
    assert "summonpot:managed:start" in text


def test_reinstalling_replaces_the_block_rather_than_appending(tmp_path: Path):
    for _ in range(3):
        runner.invoke(
            app, ["add", "skills", "--agent", "codex", "--path", str(tmp_path)]
        )

    assert (tmp_path / "AGENTS.md").read_text().count("summonpot:managed:start") == 1


def test_agents_are_detected_from_existing_configuration(tmp_path: Path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".clinerules").mkdir()

    assert set(detect_agents(tmp_path)) == {Agent.claude, Agent.cline}


def test_install_without_an_agent_uses_what_the_project_already_has(tmp_path: Path):
    (tmp_path / ".cursor").mkdir()

    result = runner.invoke(app, ["add", "skills", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / ".cursor/rules/summonpot.mdc").is_file()
    assert not (tmp_path / ".claude").exists()


def test_install_with_nothing_to_detect_explains_the_choices(tmp_path: Path):
    result = runner.invoke(app, ["add", "skills", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "--agent" in result.output
    assert "claude" in result.output
