"""Level 1: a minimal typed agentic endpoint."""

from typing import Literal

from pydantic import BaseModel, Field

from summonpot import Summon


class ReviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class ReviewResponse(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    summary: str


summon = Summon("minimal-review")


@summon("/review")
def review(request: ReviewRequest) -> ReviewResponse:
    """Classify the text's sentiment and summarize it in one short sentence."""
    ...


if __name__ == "__main__":
    summon.serve(host="127.0.0.1", port=8000)
