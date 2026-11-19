from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import logging
from typing import Any

from langchain.agents import AgentState
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.types import Command

from utils import bank_data
from utils.agent_spec import AgentFactory
from utils.guardrails import (
    access_denied_reply,
    check_endpoint_access,
)
from utils.offsite_images import image_content_block, image_legend

duckduckgo_client = DuckDuckGoSearchResults(output_format="string")


def search_web(query: str) -> str:
    """Search the web for information."""
    return duckduckgo_client.invoke(query)


web_search = tool("web_search")(search_web)


@dataclass
class SupportContext:
    user_id: str
    locale: str = "en"
    customer_tier: str = "standard"
    refund_limit: float = 50.0


class CustomerState(AgentState):
    ticket_id: str | None
    issue_category: str | None
    status: str | None


def create_customer_support_tools() -> list[Any]:
    """Create the tools used by the customer support agent."""

    @tool
    def get_support_policy(runtime: ToolRuntime[SupportContext]) -> str:
        """Return the support policy for the current user and runtime context."""
        return (
            f"User {runtime.context.user_id} is a "
            f"{runtime.context.customer_tier} customer. The maximum self-service "
            f"refund is {runtime.context.refund_limit:.2f}."
        )

    @tool
    def update_ticket(
        ticket_id: str,
        issue_category: str,
        status: str,
        runtime: ToolRuntime[SupportContext, CustomerState],
    ) -> Command:
        """Store ticket details in conversation state."""
        return Command(
            update={
                "ticket_id": ticket_id,
                "issue_category": issue_category,
                "status": status,
                "messages": [
                    ToolMessage(
                        content=f"Ticket {ticket_id} updated to {status}.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    @tool
    def read_ticket(runtime: ToolRuntime[SupportContext, CustomerState]) -> str:
        """Read the ticket details accumulated in conversation state."""
        ticket_id = runtime.state.get("ticket_id")
        if not ticket_id:
            return "No ticket has been created yet."
        return (
            f"Ticket {ticket_id}: "
            f"{runtime.state.get('issue_category', 'unknown issue')}, "
            f"status {runtime.state.get('status', 'unknown')}."
        )

    return [get_support_policy, update_ticket, read_ticket]


def create_offsite_tools(
    venue_agent: Any,
    catering_agent: Any,
    agenda_agent: Any,
    image_paths: dict[str, Path],
) -> list[Any]:
    """Create coordinator tools bound to specialist agents and local images."""

    @tool
    def choose_venue(runtime: ToolRuntime) -> str:
        """Review venue photos and recommend the best plus an alternative."""
        destination = runtime.state.get("destination", "the destination")
        content: list[Any] = [
            {
                "type": "text",
                "text": (
                    f"Review these candidate offsite venues in {destination} and "
                    "recommend the best-looking one and an alternative."
                ),
            },
            {"type": "text", "text": "Option A:"},
            image_content_block(image_paths["venue_good_1.jpg"]),
            {"type": "text", "text": "Option B:"},
            image_content_block(image_paths["venue_good_2.jpg"]),
            {"type": "text", "text": "Option C:"},
            image_content_block(image_paths["venue_bad_1.jpg"]),
            {"type": "text", "text": "Option D:"},
            image_content_block(image_paths["venue_bad_2.jpg"]),
        ]
        response = venue_agent.invoke({"messages": [HumanMessage(content=content)]})
        legend = image_legend(
            {
                "Option A": "venue_good_1.jpg",
                "Option B": "venue_good_2.jpg",
                "Option C": "venue_bad_1.jpg",
                "Option D": "venue_bad_2.jpg",
            },
            image_paths,
        )
        return f"{response['messages'][-1].content}\n\n{legend}"

    @tool
    def choose_catering(runtime: ToolRuntime) -> str:
        """Review meal photos and recommend the best plus an alternative."""
        content: list[Any] = [
            {
                "type": "text",
                "text": (
                    "Review these candidate catering meals and recommend the "
                    "best-looking one and an alternative."
                ),
            },
            {"type": "text", "text": "Option A:"},
            image_content_block(image_paths["meal_good_1.jpg"]),
            {"type": "text", "text": "Option B:"},
            image_content_block(image_paths["meal_good_2.jpg"]),
            {"type": "text", "text": "Option C:"},
            image_content_block(image_paths["meal_bad_1.jpg"]),
            {"type": "text", "text": "Option D:"},
            image_content_block(image_paths["meal_bad_2.jpg"]),
        ]
        response = catering_agent.invoke({"messages": [HumanMessage(content=content)]})
        legend = image_legend(
            {
                "Option A": "meal_good_1.jpg",
                "Option B": "meal_good_2.jpg",
                "Option C": "meal_bad_1.jpg",
                "Option D": "meal_bad_2.jpg",
            },
            image_paths,
        )
        return f"{response['messages'][-1].content}\n\n{legend}"

    @tool
    def plan_agenda(runtime: ToolRuntime) -> str:
        """Draft the agenda for the objective and attendee count."""
        objective = runtime.state.get("objective", "team alignment")
        attendee_count = runtime.state.get("attendee_count", "the team")
        query = (
            f"Draft a one-day offsite agenda for {attendee_count} attendees with "
            f"the objective: {objective}."
        )
        response = agenda_agent.invoke({"messages": [HumanMessage(content=query)]})
        return response["messages"][-1].content

    @tool
    def update_state(
        destination: str,
        attendee_count: str,
        objective: str,
        runtime: ToolRuntime,
    ) -> Command:
        """Record the destination, attendee count, and objective in agent state."""
        return Command(
            update={
                "destination": destination,
                "attendee_count": attendee_count,
                "objective": objective,
                "messages": [
                    ToolMessage(
                        content="Successfully recorded offsite details.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return [update_state, choose_venue, choose_catering, plan_agenda]


@dataclass
class BranchContext:
    officer_id: str
    branch_id: str


class BranchState(AgentState):
    current_customer_id: str | None
    matched_endpoint: dict[str, Any] | None


_NON_SPENDING_CATEGORIES = {"transfer_out", "deposit_placement"}
SPENDING_PERIODS = (
    "today", "yesterday", "this_week", "last_week", "this_month", "last_month",
    "last_7_days", "last_30_days", "this_year", "all",
)


def resolve_period(period: str, today: date | None = None) -> tuple[date | None, date | None]:
    """Map a named period to inclusive (since, until) dates; weeks start Monday."""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    last_month_end = month_start - timedelta(days=1)
    return {
        "today": (today, today),
        "yesterday": (today - timedelta(days=1),) * 2,
        "this_week": (week_start, today),
        "last_week": (week_start - timedelta(days=7), week_start - timedelta(days=1)),
        "this_month": (month_start, today),
        "last_month": (last_month_end.replace(day=1), last_month_end),
        "last_7_days": (today - timedelta(days=6), today),
        "last_30_days": (today - timedelta(days=29), today),
        "this_year": (today.replace(month=1, day=1), today),
        "all": (None, None),
    }[period]


def create_account_specialist_tools(customer_id: str) -> list[Any]:
    """Create a tool belt scoped to one customer's accounts and transactions."""

    @tool
    def list_accounts() -> str:
        """List the current customer's accounts with type, product and balance."""
        accounts = bank_data.get_accounts(customer_id)
        if not accounts:
            return "No accounts found for this customer."
        return "\n".join(
            f"- {a.account_id} ({a.account_type}, {a.product_name}): "
            f"{a.balance:,.0f} {a.currency}"
            for a in accounts
        )

    @tool
    def get_transaction_history(
        account_id: str,
        min_amount: float | None = None,
        since_iso_date: str | None = None,
    ) -> str:
        """Return recent transactions for one of this customer's accounts.

        account_id must be one of this customer's own account ids (from
        list_accounts). min_amount filters to transactions whose absolute
        amount is at least that value. since_iso_date (YYYY-MM-DD) filters to
        transactions booked on or after that date.
        """
        owned_account_ids = {a.account_id for a in bank_data.get_accounts(customer_id)}
        if account_id not in owned_account_ids:
            return f"Account {account_id} does not belong to this customer."
        try:
            since = date.fromisoformat(since_iso_date) if since_iso_date else None
        except ValueError:
            return "Invalid since_iso_date; use the YYYY-MM-DD format."
        transactions = bank_data.get_transactions(
            account_id, min_amount=min_amount, since=since
        )
        if not transactions:
            return "No matching transactions."
        return "\n".join(
            f"- {t.booking_date.isoformat()} {t.amount:+,.0f} {t.currency} "
            f"— {t.description} ({t.category})"
            + (f" | partner: {t.counterparty}" if t.counterparty else "")
            + (f" | közlemény: {t.reference}" if t.reference else "")
            for t in transactions
        )

    @tool
    def summarize_spending(
        period: str | None = None,
        since_iso_date: str | None = None,
        until_iso_date: str | None = None,
    ) -> str:
        """Total spending (outgoing debits) across all of this customer's accounts.

        Sums negative transaction amounts per currency and category, excluding
        internal money movements (transfer_out, deposit_placement).

        period is one of: today, yesterday, this_week (from Monday), last_week,
        this_month, last_month, last_7_days, last_30_days, this_year, all.
        Prefer it for relative expressions (ma, ezen a héten, ebben a hónapban);
        it is resolved against the real current date. For an explicit range use
        since_iso_date / until_iso_date (YYYY-MM-DD, inclusive) instead. With
        nothing given, all available history is used.
        """
        if period:
            if period not in SPENDING_PERIODS:
                return f"Unknown period. Use one of: {', '.join(SPENDING_PERIODS)}."
            since, until = resolve_period(period)
        else:
            try:
                since = date.fromisoformat(since_iso_date) if since_iso_date else None
                until = date.fromisoformat(until_iso_date) if until_iso_date else None
            except ValueError:
                return "Invalid date; use the YYYY-MM-DD format."
        label = (
            f"{since.isoformat() if since else 'start'} to "
            f"{until.isoformat() if until else 'latest'}"
        )
        totals: dict[str, dict[str, float]] = {}
        for account in bank_data.get_accounts(customer_id):
            for t in bank_data.get_transactions(account.account_id, since=since):
                if t.amount >= 0 or t.category in _NON_SPENDING_CATEGORIES:
                    continue
                if until is not None and t.booking_date > until:
                    continue
                by_cat = totals.setdefault(t.currency, {})
                by_cat[t.category] = by_cat.get(t.category, 0.0) + -t.amount
        if not totals:
            return f"No spending found for {label}."
        lines = [f"Period: {label}"]
        for currency, by_cat in totals.items():
            lines.append(f"Total spending: {sum(by_cat.values()):,.0f} {currency}")
            for cat, amount in sorted(by_cat.items(), key=lambda kv: -kv[1]):
                lines.append(f"- {cat}: {amount:,.0f} {currency}")
        return "\n".join(lines)

    return [list_accounts, get_transaction_history, summarize_spending]


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


SPECIALIST_RECURSION_LIMIT = 60
SPECIALIST_FAILURE_REPLY = (
    "The specialist could not answer this question right now. Do not guess - "
    "tell the officer the information is temporarily unavailable."
)
_logger = logging.getLogger(__name__)


def _specialist_gate(state: BranchState) -> str | None:
    """Deterministic pre-checks shared by both specialist wrapper tools.

    Returns a fixed reply when the specialist must not run: no customer is
    selected, or the customer selected *now* (possibly earlier in this same
    turn) is not entitled to the endpoint the router matched. Re-checking
    here, instead of trusting the router's annotation or the coordinator's
    prompt, keeps the entitlement rule enforced in code even when the
    customer is selected mid-turn.
    """
    customer_id = state.get("current_customer_id")
    if not customer_id:
        return "No customer is currently selected. Call select_customer first."
    matched = state.get("matched_endpoint")
    if matched is not None and check_endpoint_access(customer_id, matched):
        return f"ACCESS DENIED - relay this verbatim and stop: {access_denied_reply(matched)}"
    return None


def _run_specialist(agent: Any, question: str) -> str:
    """Invoke a specialist with a bounded loop; fall back to a fixed reply on
    any failure (recursion limit, provider error, timeout) instead of letting
    the coordinator improvise."""
    try:
        response = agent.invoke(
            {"messages": [HumanMessage(content=question)]},
            config={"recursion_limit": SPECIALIST_RECURSION_LIMIT},
        )
    except Exception:
        _logger.exception("Specialist call failed")
        return SPECIALIST_FAILURE_REPLY
    return response["messages"][-1].content


def create_branch_tools(
    account_factory: AgentFactory,
    product_factory: AgentFactory,
) -> list[Any]:
    """Create the coordinator's own tools: customer lookup plus two specialist
    wrappers. Unlike ``create_offsite_tools`` (whose specialists have static
    tools because the data - the candidate images - is fixed ahead of time),
    the account/product specialists here must be scoped to whichever customer
    is currently selected, so each wrapper tool builds a fresh specialist
    agent with customer-scoped tools on every call, from the agent's own
    Markdown definition (``AgentFactory``, model built once at startup).
    """

    @tool
    def list_customers() -> str:
        """List every customer available to select in this demo branch session."""
        return "\n".join(
            f"- {c.customer_id}: {c.full_name} (born {c.date_of_birth.isoformat()})"
            for c in bank_data.list_customers()
        )

    @tool
    def select_customer(
        name_or_id: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> Command:
        """Select the customer currently at the branch desk, by name or id."""
        customer = bank_data.find_customer(name_or_id)
        if customer is None:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content=(
                                f"No customer matches '{name_or_id}'. "
                                "Use list_customers to see available customers."
                            ),
                            tool_call_id=runtime.tool_call_id,
                        )
                    ]
                }
            )
        return Command(
            update={
                "current_customer_id": customer.customer_id,
                "messages": [
                    ToolMessage(
                        content=(
                            f"Selected customer {customer.full_name} "
                            f"({customer.customer_id})."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    @tool
    def ask_account_specialist(
        question: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> str:
        """Ask the account/transactions specialist about the selected customer's
        balances or transaction history."""
        if (blocked := _specialist_gate(runtime.state)) is not None:
            return blocked
        customer_id = runtime.state["current_customer_id"]
        account_agent = account_factory.build(create_account_specialist_tools(customer_id))
        return _run_specialist(account_agent, question)

    @tool
    def ask_product_specialist(
        question: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> str:
        """Ask the product/offers specialist about the catalog or the selected
        customer's personalized discounts."""
        if (blocked := _specialist_gate(runtime.state)) is not None:
            return blocked
        customer_id = runtime.state["current_customer_id"]
        product_agent = product_factory.build(create_product_specialist_tools(customer_id))
        return _run_specialist(product_agent, question)

    return [list_customers, select_customer, ask_account_specialist, ask_product_specialist]
