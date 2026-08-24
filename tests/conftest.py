"""Shared test fixtures and utilities for summonpot."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_runtime():
    """Return a Summon whose Runtime is replaced with a mock.

    Lets tests exercise endpoint registration and server building
    without making real LLM calls.
    """
    from summonpot.summon import Summon

    summon = Summon("test-summon")
    original_runtime = summon._runtime
    mock = AsyncMock()

    def install(mock_response="agent response"):
        async def fake_call(endpoint, params):
            return mock_response

        mock.call.side_effect = fake_call
        summon._runtime = mock
        return summon

    yield install
    summon._runtime = original_runtime
