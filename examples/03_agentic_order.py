"""Level 3: bounded agentic choices with a required side effect."""

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field

from summonpot import Depends, Pot, Required

INVENTORY = {"red-mug": 0, "blue-mug": 8, "green-mug": 3}
SUBSTITUTES = {"red-mug": ["blue-mug", "green-mug"]}
ORDER_LOG = Path(os.environ.get("SUMMONPOT_ORDER_LOG", "/tmp/summonpot-orders.jsonl"))


class OrderRequest(BaseModel):
    customer_id: str = Field(pattern=r"^customer-[0-9]+$")
    sku: str
    quantity: int = Field(ge=1, le=5)
    allow_substitute: bool = True


class OrderResponse(BaseModel):
    order_id: str
    selected_sku: str
    substituted: bool
    status: str


def check_inventory(sku: str, quantity: int) -> dict[str, object]:
    """Return exact inventory availability for one SKU and quantity."""
    available_units = INVENTORY.get(sku, 0)
    return {
        "sku": sku,
        "requested_units": quantity,
        "available_units": available_units,
        "available": available_units >= quantity,
    }


def find_substitute(sku: str, quantity: int) -> dict[str, object] | None:
    """Return the first approved substitute with enough inventory, if one exists."""
    for candidate in SUBSTITUTES.get(sku, []):
        if INVENTORY.get(candidate, 0) >= quantity:
            return {"sku": candidate, "available_units": INVENTORY[candidate]}
    return None


def create_order(customer_id: str, sku: str, quantity: int) -> dict[str, str]:
    """Persist an order for an in-stock SKU and return its receipt."""
    if INVENTORY.get(sku, 0) < quantity:
        raise ValueError(f"Not enough inventory for {sku!r}")

    order_id = f"order-{customer_id.removeprefix('customer-')}-{sku}-{quantity}"
    receipt = {
        "order_id": order_id,
        "customer_id": customer_id,
        "sku": sku,
        "quantity": quantity,
        "status": "created",
    }
    with ORDER_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, sort_keys=True) + "\n")
    return {"order_id": order_id, "status": "created"}


pot = Pot("agentic-orders")


@pot.summon("/orders")
def fulfill_order(
    request: OrderRequest,
    inventory=Depends(check_inventory),
    substitution=Depends(find_substitute),
    creation=Required(create_order),
) -> OrderResponse:
    """Fulfill the requested order. Check inventory first. If it is unavailable and substitution is allowed, choose an approved in-stock substitute. Create exactly one order and report whether its SKU differs from the requested SKU."""
    raise NotImplementedError


if __name__ == "__main__":
    pot.serve(host="127.0.0.1", port=8000)
