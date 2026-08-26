"""Presentation guards for the repository's primary adoption surface."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def test_readme_leads_with_the_enforced_authority_boundary():
    readme = README.read_text()
    introduction = readme.split("## Quick start", 1)[0]

    assert "explicit model authority" in introduction.lower()
    assert "FromRequest" in introduction
    assert "AgentChoice" in introduction
    assert "Exactly(1)" in introduction
    assert "summonpot.png" not in introduction
    assert "every <code>@summon(...)</code> request uses" in introduction


def test_readme_prioritizes_adoption_over_release_history():
    readme = README.read_text()

    assert readme.index("## Quick start") < readme.index(
        "## Migrating from the 0.5 API"
    )
    assert "### New in 0.6.0" not in readme
    assert "### New in 0.5.0" not in readme


def test_readme_shows_the_authority_transformation():
    readme = README.read_text()
    diagram = ROOT / "docs" / "assets" / "authority-boundary.svg"

    assert (
        "https://raw.githubusercontent.com/tugrulguner/summonpot/"
        "014814f7b304da5309afb43d22446bd6dda15c7d/"
        "docs/assets/authority-boundary.svg"
    ) in readme
    assert diagram.is_file()
    content = diagram.read_text()
    assert "Validated request" in content
    assert "Model supplies" in content
    assert "Summonpot invokes" in content
    assert "Validated response" in content
    assert "exactly-once operation" not in content


def test_readme_distinguishes_tool_schema_hiding_from_prompt_secrecy():
    readme = README.read_text()

    assert "tool-schema hiding is not prompt secrecy" in readme
    assert "Other operation shapes continue to expose" in readme
