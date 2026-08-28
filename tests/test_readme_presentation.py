"""Presentation guards for the repository's primary adoption surface."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"


def test_readme_leads_with_unified_deterministic_and_agentic_flows():
    readme = README.read_text(encoding="utf-8")
    introduction = readme.split("## Quick start", 1)[0]
    normalized_introduction = " ".join(introduction.lower().split())

    assert "deterministic operations and agentic decisions" in normalized_introduction
    assert "share one framework" in normalized_introduction
    assert (
        "every `@summon(...)` request still uses the configured model runtime"
        in normalized_introduction
    )
    assert (
        "automatic no-model execution for fully resolved declarations remains planned"
        in normalized_introduction
    )
    assert "FromRequest" in introduction
    assert "AgentChoice" in introduction
    assert "Exactly(1)" in introduction
    assert "summonpot.png" not in introduction
    assert "published 0.6.0 predates the bound runtime" in normalized_introduction


def test_readme_prioritizes_adoption_over_release_history():
    readme = README.read_text(encoding="utf-8")
    quick_start = readme.split("## Quick start", 1)[1].split("## Why summonpot?", 1)[0]

    assert readme.index("## Quick start") < readme.index(
        "## Migrating from the 0.5 API"
    )
    assert (
        "git+https://github.com/tugrulguner/summonpot.git@"
        "4819a8bc0503b3d4f3995fd76a6f678abd07047d"
    ) in quick_start
    assert "### New in 0.6.0" not in readme
    assert "### New in 0.5.0" not in readme


def test_readme_shows_the_authority_transformation():
    readme = README.read_text(encoding="utf-8")
    diagram = ROOT / "docs" / "assets" / "authority-boundary.svg"

    assert (
        "https://raw.githubusercontent.com/tugrulguner/summonpot/"
        "014814f7b304da5309afb43d22446bd6dda15c7d/"
        "docs/assets/authority-boundary.svg"
    ) in readme
    assert diagram.is_file()
    content = diagram.read_text(encoding="utf-8")
    assert "Validated request" in content
    assert "Model supplies" in content
    assert "Summonpot invokes" in content
    assert "Validated response" in content
    assert "exactly-once operation" not in content


def test_readme_distinguishes_tool_schema_hiding_from_prompt_secrecy():
    readme = README.read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())

    assert "tool-schema hiding is not prompt secrecy" in normalized_readme
    assert "Other operation shapes continue to expose" in normalized_readme
