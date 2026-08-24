"""Level 2: an endpoint backed by an exact required calculation."""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from summonpot import Pot, Required


class QuoteRequest(BaseModel):
    unit_price_cents: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)
    tax_rate_percent: Decimal = Field(ge=0, le=30)


class QuoteResponse(BaseModel):
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    explanation: str


def calculate_quote(
    unit_price_cents: int,
    quantity: int,
    tax_rate_percent: Decimal,
) -> dict[str, int]:
    """Calculate an exact quote in integer cents using half-up tax rounding."""
    subtotal = unit_price_cents * quantity
    tax = (Decimal(subtotal) * tax_rate_percent / Decimal(100)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return {
        "subtotal_cents": subtotal,
        "tax_cents": int(tax),
        "total_cents": subtotal + int(tax),
    }


pot = Pot("required-calculation")


@pot.summon("/quotes")
def create_quote(
    request: QuoteRequest,
    calculation=Required(calculate_quote),
) -> QuoteResponse:
    """Call calculate_quote and return its exact monetary values with a brief explanation. Never perform the calculation yourself."""
    ...


if __name__ == "__main__":
    pot.serve(host="127.0.0.1", port=8000)
