"""Product specialist tools: product catalog, personalized offers, existing loans."""

from typing import Any

from langchain.tools import tool

from data import bank_data


def create_product_specialist_tools(customer_id: str) -> list[Any]:
    """Create a tool belt scoped to the catalog and one customer's offers."""

    @tool
    def list_catalog() -> str:
        """List every product in the bank's shared catalog with headline rates."""
        return "\n".join(
            f"- {p.product_id} {p.name} ({p.category}): "
            f"{p.rate_label} {p.headline_rate}% — {p.description}"
            for p in bank_data.list_products()
        )

    @tool
    def list_personalized_offers() -> str:
        """List personalized discounts/offers currently available to this customer."""
        offers = bank_data.get_offers(customer_id)
        if not offers:
            return "No personalized offers for this customer right now."
        lines = []
        for offer in offers:
            product = bank_data.get_product(offer.product_id)
            product_name = product.name if product else offer.product_id
            lines.append(
                f"- {product_name}: {offer.description} ({offer.discount_detail}), "
                f"valid until {offer.valid_until.isoformat()}. Reason: {offer.reason}"
            )
        return "\n".join(lines)

    @tool
    def list_existing_loans() -> str:
        """List this customer's existing loans: balance, installment, rate, dates."""
        loans = bank_data.get_loans(customer_id)
        if not loans:
            return "This customer has no existing loans."
        return "\n".join(
            f"- {loan.loan_id} {loan.name}: original {loan.original_amount:,.0f} "
            f"{loan.currency}, outstanding {loan.outstanding_balance:,.0f}, "
            f"installment {loan.monthly_payment:,.0f}/month from {loan.repayment_account_id}, "
            f"rate {loan.interest_rate}%, next payment {loan.next_payment_date.isoformat()}, "
            f"matures {loan.maturity_date.isoformat()}"
            for loan in loans
        )

    return [list_catalog, list_personalized_offers, list_existing_loans]
