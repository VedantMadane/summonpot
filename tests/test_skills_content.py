"""The shipped skill is documentation; these guard what it must keep saying.

Each assertion pins a rule the framework enforces at registration. If the framework
changes, the skill has to change with it, and this test is what forces that.
"""

from __future__ import annotations

import pytest

from summonpot.skills.content import SKILL_DESCRIPTION, SKILL_NAME, skill_body


def test_skill_ships_inside_the_package():
    assert skill_body().strip()
    assert SKILL_NAME == "summonpot"


def test_description_says_when_to_load_it():
    """An agent reads only the description when deciding to open the skill."""
    assert "@pot.summon" in SKILL_DESCRIPTION
    assert len(SKILL_DESCRIPTION) < 500


@pytest.mark.parametrize(
    "rule",
    [
        "raise NotImplementedError",  # the body is never executed
        "docstring",  # required, and it is the goal
        "start with `/`",  # path validation
        "(path, method)",  # duplicate-route rule
        "TYPE_CHECKING",  # unresolvable annotations are rejected
        "unbound method",  # capability must be bound
        "stream=True",  # not implemented, raises
        "query-string",  # bodyless methods
        "SUMMONPOT_MODEL=test",  # keyless trial
        "worker thread",  # thread-affine resources
        "usage_limits",  # bounding a call
    ],
)
def test_skill_documents_an_enforced_rule(rule):
    assert rule in skill_body()


@pytest.mark.parametrize("status", ["422", "429", "502", "504"])
def test_skill_documents_the_failure_statuses(status):
    assert status in skill_body()
