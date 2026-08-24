"""Level 6: a multi-file support service with bounded capabilities."""

from support_models import (
    CustomerRecord,
    SupportRequest,
    SupportResponse,
    TicketReceipt,
)
from support_operations import create_ticket, load_customer, load_policy

from summonpot import (
    AgentChoice,
    Exactly,
    FromRequest,
    FromResult,
    Operation,
    Required,
    Summon,
    UsageLimits,
)
from summonpot.runtime import Runtime

runtime = Runtime(
    retries=3,
    usage_limits=UsageLimits(request_limit=10, total_tokens_limit=12_000),
    timeout=60.0,
)
summon = Summon("support-service", runtime=runtime)

customer_lookup = Operation(
    load_customer,
    bind={"customer_id": FromRequest("customer_id")},
    output=CustomerRecord,
)
policy_lookup = Operation(
    load_policy,
    bind={"topic": AgentChoice()},
    output=str,
)
ticket_creation = Operation(
    create_ticket,
    bind={
        "customer_id": FromResult(customer_lookup, "customer_id"),
        "priority": AgentChoice(),
        "summary": AgentChoice(),
    },
    output=TicketReceipt,
    after=(customer_lookup, policy_lookup),
)


@summon("/support")
def handle_support(
    request: SupportRequest,
    customer=Required(customer_lookup),
    policy=Required(policy_lookup),
    ticket=Required(ticket_creation, calls=Exactly(1)),
) -> SupportResponse:
    """Handle the customer's support message. Load the customer. Select the relevant approved policy. Mark confirmed outages urgent and everything else normal. Create exactly one ticket, then write a brief reply grounded in the customer record and policy."""
    ...


if __name__ == "__main__":
    summon.serve(host="127.0.0.1", port=8000)
