"""Request and response contracts for the support example."""

from typing import Literal

from pydantic import BaseModel, Field


class SupportRequest(BaseModel):
    customer_id: str = Field(pattern=r"^customer-[0-9]+$")
    message: str = Field(min_length=10, max_length=2_000)


class SupportResponse(BaseModel):
    ticket_id: str
    priority: Literal["normal", "urgent"]
    reply: str
    account_plan: str
