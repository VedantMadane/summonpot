"""Tests for the canonical Summon application API."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_summon_is_the_public_application_type():
    from summonpot import Summon

    summon = Summon("svc")

    assert summon.name == "svc"
    assert type(summon).__name__ == "Summon"
    assert repr(summon).startswith("Summon('svc',")


def test_summon_instance_is_the_endpoint_decorator():
    from summonpot import Summon

    summon = Summon("svc")

    @summon("/research")
    def research(query: str) -> str:
        """Research this topic."""
        ...

    assert len(summon.endpoints) == 1
    assert summon.endpoints[0].path == "/research"
    assert summon.endpoints[0].name == "research"


def test_pot_is_not_part_of_the_package_root_api():
    import summonpot

    assert not hasattr(summonpot, "Pot")
    assert "Pot" not in summonpot.__all__


def test_cli_loads_the_module_summon_variable(tmp_path: Path):
    from summonpot.cli import _load_summon

    source = tmp_path / "app.py"
    source.write_text("from summonpot import Summon\nsummon = Summon('loaded')\n")

    loaded = _load_summon(str(source))

    assert loaded.name == "loaded"


def test_public_surfaces_use_the_summon_application_vocabulary():
    surfaces = [
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "src/summonpot/templates/skills/summonpot.md",
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.py")),
    ]
    stale = {
        str(path.relative_to(ROOT)): sorted(
            set(
                re.findall(
                    r"\bPot\b|@pot\.summon|@summon\.summon|\bpot\s*=",
                    path.read_text(),
                )
            )
        )
        for path in surfaces
        if re.search(
            r"\bPot\b|@pot\.summon|@summon\.summon|\bpot\s*=", path.read_text()
        )
    }

    assert stale == {}
