from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.chat_models import BaseChatModel
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.types import Command

from utils import bank_data, endpoint_catalog
from utils.guardrails import build_guardrail_middleware
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


def create_endpoint_router_tools() -> list[Any]:
    """Create the endpoint-router agent's single tool.

    Unlike the account/product specialist tool belts, this isn't scoped to a
    customer id — the catalog is the same for everyone, and the
    customer-specific entitlement check happens later, in
    ``EndpointAccessMiddleware``.
    """

    @tool
    def search_endpoint_catalog(
        query: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> Command:
        """Search the web banking app's REST endpoint catalog for the single
        best match to the officer's question."""
        matches = endpoint_catalog.search_endpoints(query)
        if not matches:
            return Command(
                update={
                    "matched_endpoint": None,
                    "messages": [
                        ToolMessage(
                            content="No matching endpoint found in the catalog.",
                            tool_call_id=runtime.tool_call_id,
                        )
                    ],
                }
            )
        best = matches[0]
        return Command(
            update={
                "matched_endpoint": asdict(best),
                "messages": [
                    ToolMessage(
                        content=(
                            f"Best match: {best.method} {best.path} — "
                            f"{best.description} (menu: {best.menu_path}, "
                            f"requires {best.required_entitlement} tier)."
                        ),
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    return [search_endpoint_catalog]


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
        since = date.fromisoformat(since_iso_date) if since_iso_date else None
        transactions = bank_data.get_transactions(
            account_id, min_amount=min_amount, since=since
        )
        if not transactions:
            return "No matching transactions."
        return "\n".join(
            f"- {t.booking_date.isoformat()} {t.amount:+,.0f} {t.currency} "
            f"— {t.description} ({t.category})"
            for t in transactions
        )

    return [list_accounts, get_transaction_history]


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

    return [list_catalog, list_personalized_offers]


def create_branch_tools(
    account_model: BaseChatModel,
    account_prompt: str,
    product_model: BaseChatModel,
    product_prompt: str,
) -> list[Any]:
    """Create the coordinator's own tools: customer lookup plus two specialist
    wrappers. Unlike ``create_offsite_tools`` (whose specialists have static
    tools because the data - the candidate images - is fixed ahead of time),
    the account/product specialists here must be scoped to whichever customer
    is currently selected, so each wrapper tool builds a fresh specialist
    agent with customer-scoped tools on every call, from the model+prompt
    pair loaded once at startup.
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
        customer_id = runtime.state.get("current_customer_id")
        if not customer_id:
            return "No customer is currently selected. Call select_customer first."
        account_agent = create_agent(
            model=account_model,
            tools=create_account_specialist_tools(customer_id),
            system_prompt=account_prompt,
            middleware=build_guardrail_middleware(),
        )
        response = account_agent.invoke({"messages": [HumanMessage(content=question)]})
        return response["messages"][-1].content

    @tool
    def ask_product_specialist(
        question: str, runtime: ToolRuntime[BranchContext, BranchState]
    ) -> str:
        """Ask the product/offers specialist about the catalog or the selected
        customer's personalized discounts."""
        customer_id = runtime.state.get("current_customer_id")
        if not customer_id:
            return "No customer is currently selected. Call select_customer first."
        product_agent = create_agent(
            model=product_model,
            tools=create_product_specialist_tools(customer_id),
            system_prompt=product_prompt,
            middleware=build_guardrail_middleware(),
        )
        response = product_agent.invoke({"messages": [HumanMessage(content=question)]})
        return response["messages"][-1].content

    return [list_customers, select_customer, ask_account_specialist, ask_product_specialist]
