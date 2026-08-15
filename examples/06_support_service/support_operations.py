"""Application-owned operations exposed to the support endpoint."""

import json
import os
from pathlib import Path
from typing import Literal

CUSTOMERS = {
    "customer-1": {"name": "Ada", "plan": "enterprise"},
    "customer-2": {"name": "Grace", "plan": "starter"},
}
TICKET_LOG = Path(
    os.environ.get("SUMMONPOT_TICKET_LOG", "/tmp/summonpot-support-tickets.jsonl")
)


def load_customer(customer_id: str) -> dict[str, str]:
    """Load the exact customer name and plan for one customer identifier."""
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise ValueError(f"Unknown customer: {customer_id}")
    return {"customer_id": customer_id, **customer}


def load_policy(topic: Literal["billing", "outage", "general"]) -> str:
    """Load the approved support policy for one topic."""
    policies = {
        "billing": "Acknowledge the charge and request its invoice identifier.",
        "outage": "Treat a confirmed service outage as urgent and give no invented ETA.",
        "general": "Answer briefly and ask one focused follow-up when needed.",
    }
    return policies[topic]


def create_ticket(
    customer_id: str,
    priority: Literal["normal", "urgent"],
    summary: str,
) -> dict[str, str]:
    """Persist one support ticket and return its exact receipt."""
    ticket_id = f"ticket-{customer_id.removeprefix('customer-')}-{priority}"
    receipt = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "priority": priority,
        "summary": summary,
    }
    with TICKET_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    return {"ticket_id": ticket_id, "priority": priority}
