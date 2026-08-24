"""Level 5: bounded runtime configuration and a route-level model override."""

from pydantic import BaseModel, Field

from summonpot import Pot, UsageLimits
from summonpot.runtime import Runtime


class SummaryRequest(BaseModel):
    text: str = Field(min_length=20, max_length=10_000)
    max_sentences: int = Field(default=3, ge=1, le=5)


class SummaryResponse(BaseModel):
    summary: str
    key_points: list[str]


runtime = Runtime(
    retries=2,
    usage_limits=UsageLimits(request_limit=6, total_tokens_limit=8_000),
    timeout=45.0,
)
pot = Pot("bounded-summaries", runtime=runtime)


@pot.summon("/summaries")
def summarize(request: SummaryRequest) -> SummaryResponse:
    """Summarize the text within max_sentences and extract up to five concrete key points."""
    ...


@pot.summon("/summaries/fast", model="openai:gpt-4o-mini")
def summarize_fast(request: SummaryRequest) -> SummaryResponse:
    """Produce a concise summary within max_sentences and extract up to three key points."""
    ...


if __name__ == "__main__":
    pot.serve(host="127.0.0.1", port=8000)
