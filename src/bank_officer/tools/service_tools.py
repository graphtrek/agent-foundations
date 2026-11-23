"""Service specialist tools: cards, loan applications, profile, support tickets."""

from typing import Any

from langchain.tools import tool

from data import bank_data
from tools.tool_helpers import tier_denied


def create_service_specialist_tools(customer_id: str) -> list[Any]:
    """Create a tool belt scoped to one customer's cards, profile, loan
    applications and support tickets (the customer-service side)."""

    @tool
    def get_loan_application_status(application_id: str = "") -> str:
        """Status and history of this customer's loan applications; give an
        application id, or leave empty to list all of them."""
        apps = bank_data.get_loan_applications(customer_id)
        if application_id:
            apps = [a for a in apps if a.application_id == application_id]
        if not apps:
            return "No matching loan application for this customer."
        blocks = []
        for a in apps:
            product = bank_data.get_product(a.product_id)
            history = "\n".join(f"  {d} {st}: {note}" for d, st, note in a.history)
            blocks.append(
                f"- {a.application_id} {product.name if product else a.product_id}, "
                f"{a.amount:,.0f} HUF - current status: {a.history[-1][1]}\n{history}"
            )
        return "\n".join(blocks)

    @tool
    def list_cards() -> str:
        """List this customer's debit and credit cards with status and expiry."""
        cards = bank_data.get_cards(customer_id)
        if not cards:
            return "This customer has no cards."
        return "\n".join(
            f"- {c.card_id} {c.brand} ({c.kind}) {c.number}, linked account {c.account_id}, "
            f"expires {c.expires}, {c.status}"
            for c in cards
        )

    @tool
    def get_card_limits(card_id: str) -> str:
        """Daily spending/withdrawal limits and today's usage for one card
        (premium tier and above)."""
        if (denied := tier_denied(customer_id, "ep-cards-get-limits")) is not None:
            return denied
        limits = bank_data.get_card_limits(customer_id, card_id)
        if limits is None:
            return f"Card {card_id} does not belong to this customer."
        return "\n".join(f"- {t}: limit {lim:,.0f} HUF, used today {used:,.0f} HUF" for t, lim, used in limits)

    @tool
    def get_customer_profile() -> str:
        """The selected customer's profile and contact information."""
        c = bank_data.find_customer(customer_id)
        if c is None:
            return "Customer not found."
        return (
            f"{c.customer_id}: {c.full_name}, born {c.date_of_birth.isoformat()}, phone {c.phone}, "
            f"email {c.email}, home branch {c.home_branch_id}, entitlement tier {c.entitlement_tier}"
        )

    @tool
    def get_support_ticket_status(ticket_id: str = "") -> str:
        """Status and history of this customer's support tickets; give a ticket
        id, or leave empty to list all of them."""
        tickets = bank_data.get_support_tickets(customer_id)
        if ticket_id:
            tickets = [t for t in tickets if t.ticket_id == ticket_id]
        if not tickets:
            return "No matching support ticket for this customer."
        return "\n".join(
            f"- {t.ticket_id} {t.subject} - current status: {t.history[-1][1]}\n"
            + "\n".join(f"  {when} {st} ({by}): {msg}" for when, st, by, msg in t.history)
            for t in tickets
        )

    return [
        list_cards,
        get_card_limits,
        get_loan_application_status,
        get_customer_profile,
        get_support_ticket_status,
    ]
