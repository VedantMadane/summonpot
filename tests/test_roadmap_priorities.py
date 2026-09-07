"""Pin planned safety prerequisites without claiming they already execute."""

import re
from pathlib import Path

ROADMAP = Path(__file__).resolve().parents[1] / "ROADMAP.md"


def test_hardening_is_planned_and_precedes_execution_expansion():
    text = ROADMAP.read_text(encoding="utf-8")
    planned = text.split("## Next milestones", 1)[1].split("## Non-goals", 1)[0]
    headings = re.findall(r"^### (\d+)\. (.+)$", planned, re.MULTILINE)
    assert [int(number) for number, _ in headings] == list(range(1, 10))
    assert headings[0][1] == "Contract enforcement and input/output hardening"
    assert "planned acceptance criteria, not claims" in planned

    hardening = " ".join(planned.split("### 2.", 1)[0].split())
    for requirement in (
        "reject the unsupported declaration before serving",
        "Adding a second capability must not remove enforcement",
        "receiving operation constraints",
        "render model input only when agent execution needs it",
        "duplicate JSON keys",
        "sensitive validation inputs, provider bodies, or exception chains",
        "a copy-hook fix alone is not completion of the transport boundary",
    ):
        assert requirement in hardening


def test_chain_failure_semantics_are_not_deferred_to_adapters():
    text = ROADMAP.read_text(encoding="utf-8")
    chain = " ".join(text.split("### 2.", 1)[1].split("### 3.", 1)[0].split())
    for requirement in (
        "Failure semantics ship with the chain",
        "partial completion",
        "uncertain outcome after timeout",
        "final-output retries must not replay effects",
        "Required use alone does not prove",
        "Preserve application-provided idempotency keys",
        "Execution remains sequential initially",
    ):
        assert requirement in chain
