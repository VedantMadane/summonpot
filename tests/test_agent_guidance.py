"""Regression tests for contributor-facing agent guidance."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
REVIEW_SKILL = ROOT / ".claude/skills/review-code/SKILL.md"


def review_skill() -> str:
    return REVIEW_SKILL.read_text()


def test_review_verification_never_manipulates_the_users_stash():
    guidance = review_skill()

    assert "git stash" not in guidance
    assert "git worktree" in guidance
    assert "isolated" in guidance


def test_review_guidance_points_to_the_current_registration_entrypoint():
    guidance = review_skill()
    normalized = " ".join(guidance.split())

    assert "`Summon.__call__()`" in guidance
    assert "`src/summonpot/summon.py`" in guidance
    assert "registration entry point" in normalized
    assert "`src/summonpot/tools.py`" in guidance
    assert "`src/summonpot/_validation.py`" in guidance
    assert "`pot.py`" not in guidance
