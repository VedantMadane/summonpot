"""Shared test fixtures and utilities for summonpot."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_runtime():
    """Return a Pot whose Runtime is replaced with a mock.

    Lets tests exercise endpoint registration and server building
    without making real LLM calls.
    """
    from summonpot.pot import Pot

    pot = Pot("test-pot")
    original_runtime = pot._runtime
    mock = AsyncMock()

    def install(mock_response="agent response"):
        async def fake_call(endpoint, params):
            return mock_response

        mock.call.side_effect = fake_call
        pot._runtime = mock
        return pot

    yield install
    pot._runtime = original_runtime
