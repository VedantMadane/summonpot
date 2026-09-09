"""Keep request provenance and output-constructor limits in shipped guidance."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_custom_output_initializers_are_documented_as_registration_errors():
    for path in (
        ROOT / "docs/declarative-capabilities.md",
        ROOT / "src/summonpot/templates/skills/summonpot.md",
    ):
        text = " ".join(path.read_text(encoding="utf-8").split())
        assert "__init__" in text
        assert "nested models" in text
        assert "registration" in text.lower()
        assert "model validators" in text


def test_request_validation_provenance_is_documented_in_packaged_skill():
    text = (ROOT / "src/summonpot/templates/skills/summonpot.md").read_text(
        encoding="utf-8"
    )
    assert "HTTP request validation runs once" in text
    assert "plan-bound validated" in text
    assert "ordinary request wrappers are not trusted" in text


def test_request_copy_hook_boundary_is_documented_in_both_guides():
    for path in (
        ROOT / "docs/declarative-capabilities.md",
        ROOT / "src/summonpot/templates/skills/summonpot.md",
    ):
        text = " ".join(path.read_text(encoding="utf-8").split())
        assert "application-defined copy hooks" in text
        assert "compatibility views" in text
        assert "consumed transport" in text
        assert '"<unavailable>"' in text
        assert "non-string keys are omitted" in text
        assert "application serializers" in text
        assert "earlier body serialization" in text
        assert "custom-runtime typed views retain native values" in text
        assert "UUIDs independently reconstructed" in text
        assert "application-defined timezone callbacks are not invoked" in text
