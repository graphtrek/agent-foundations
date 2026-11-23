"""Account specialist tools: accounts, transactions, statements, payments."""

from datetime import date
from typing import Any

from langchain.tools import tool

from data import bank_data
from tools.date_resolver import SPENDING_PERIODS, resolve_period
from tools.tool_helpers import format_huf, tier_denied

NON_SPENDING_CATEGORIES = {"transfer_out", "deposit_placement"}


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
                if t.amount >= 0 or t.category in NON_SPENDING_CATEGORIES:
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

    @tool
    def get_account_details(account_id: str) -> str:
        """Details of one of this customer's accounts: type, product, balance,
        opening date, number of transactions and the last booking."""
        account = bank_data.get_account(customer_id, account_id)
        if account is None:
            return f"Account {account_id} does not belong to this customer."
        txns = bank_data.get_transactions(account_id)
        last = f"{txns[0].booking_date.isoformat()} - {txns[0].description}" if txns else "-"
        return (
            f"{account.account_id}: {account.account_type}, {account.product_name}, "
            f"balance {account.balance:,.0f} {account.currency}, opened "
            f"{account.opened_on.isoformat()}, {len(txns)} transactions on file, last booking {last}"
        )

    @tool
    def get_account_statement(account_id: str, month: str) -> str:
        """Monthly statement of one account: all items of the month plus credit,
        debit and net totals. month is YYYY-MM (e.g. 2026-10)."""
        if bank_data.get_account(customer_id, account_id) is None:
            return f"Account {account_id} does not belong to this customer."
        rows = [
            t for t in bank_data.get_transactions(account_id)
            if t.booking_date.strftime("%Y-%m") == month
        ]
        if not rows:
            return f"No statement items for {account_id} in {month}."
        rows.sort(key=lambda t: t.booking_date)
        credits = sum(t.amount for t in rows if t.amount > 0)
        debits = sum(t.amount for t in rows if t.amount < 0)
        items = "\n".join(
            f"- {t.booking_date.isoformat()} {t.amount:+,.0f} {t.currency} - {t.description}"
            for t in rows
        )
        return (
            f"Statement {account_id} {month}: {len(rows)} items, credits {credits:,.0f}, "
            f"debits {debits:,.0f}, net {credits + debits:,.0f}.\n{items}"
        )

    @tool
    def get_business_overview() -> str:
        """Consolidated overview of all business accounts and sub-accounts
        (business tier only), with each account's share of the total."""
        if (denied := tier_denied(customer_id, "ep-accounts-business-overview")) is not None:
            return denied
        rows = [(a.account_id, a.account_type, a.product_name, a.balance)
                for a in bank_data.get_accounts(customer_id)]
        rows += [(a.account_id, a.account_type, a.name, a.balance)
                 for a in bank_data.get_business_accounts(customer_id)]
        total = sum(r[3] for r in rows)
        lines = [
            f"- {i} ({t}, {n}): {b:,.0f} HUF ({100 * b / total if total else 0:.1f}%)"
            for i, t, n, b in sorted(rows, key=lambda r: -r[3])
        ]
        return f"Consolidated balance: {total:,.0f} HUF across {len(rows)} accounts.\n" + "\n".join(lines)

    @tool
    def list_scheduled_payments() -> str:
        """List this customer's scheduled, recurring and direct-debit payments."""
        payments = bank_data.get_scheduled_payments(customer_id)
        if not payments:
            return "This customer has no scheduled payments."
        return "\n".join(
            f"- {p.payment_id} {p.beneficiary}: {format_huf(p.amount)} from {p.from_account_id}, "
            f"{p.frequency}, next {p.next_execution.isoformat()}, {p.status}"
            for p in sorted(payments, key=lambda p: p.next_execution)
        )

    return [
        list_accounts,
        get_transaction_history,
        summarize_spending,
        get_account_details,
        get_account_statement,
        get_business_overview,
        list_scheduled_payments,
    ]
