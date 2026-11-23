"""Customer-independent tools: branch hours, locations, general conditions."""

from typing import Any

from langchain.tools import tool

from data import bank_data
from tools.date_resolver import resolve_date


def create_public_info_tools(customer_id: str = "") -> list[Any]:
    """Customer-independent tools (branch hours, locations, general
    conditions). ``customer_id`` is unused: the tools answer the same for
    everyone, so no customer has to be selected."""

    @tool
    def get_branch_opening_hours(when: str = "today", branch: str = "") -> str:
        """Opening hours of a branch on a given day (not customer-specific).

        ``when``: an ISO date (2026-11-23), "today", "tomorrow", "this_<weekday>"
        or "next_<weekday>" (e.g. "next_monday" = Monday of next week). ``branch``:
        branch name or id; empty lists every branch.
        """
        day = resolve_date(when)
        if day is None:
            return (
                f"Could not understand the date '{when}'. Use an ISO date, today, "
                "tomorrow, this_<weekday> or next_<weekday>."
            )
        if branch:
            found = bank_data.find_branch(branch)
            if found is None:
                names = ", ".join(b.name for b in bank_data.list_branches())
                return f"No branch matches '{branch}'. Branches: {names}."
            branches = [found]
        else:
            branches = bank_data.list_branches()
        lines = [f"Opening hours on {day.isoformat()} ({day.strftime('%A')}):"]
        for b in branches:
            hours = bank_data.get_branch_hours(b.branch_id, day)
            if hours is None:
                lines.append(f"- {b.name} ({b.address}): closed")
            else:
                opens, closes, note = hours
                lines.append(
                    f"- {b.name} ({b.address}): {opens}-{closes}" + (f" ({note})" if note else "")
                )
        return "\n".join(lines)

    @tool
    def list_branch_locations(city: str = "", postal_code: str = "") -> str:
        """Branch locations with address and map coordinates, optionally
        filtered by city or postal code (not customer-specific)."""
        found = [
            b for b in bank_data.list_branches()
            if (not city or b.city.lower() == city.strip().lower())
            and (not postal_code or b.postal_code == postal_code.strip())
        ]
        if not found:
            return "No branch matches that city / postal code."
        return "\n".join(
            f"- {b.branch_id} {b.name}: {b.postal_code} {b.city}, {b.address} "
            f"(lat {b.lat:.4f}, lon {b.lon:.4f})"
            for b in found
        )

    @tool
    def get_general_conditions(product: str = "") -> str:
        """Standard account/product terms, fees and interest conditions (not
        customer-specific); optionally filter by a product-name fragment."""
        rows = [
            r for r in bank_data.list_conditions()
            if not product or product.strip().lower() in r[0].lower()
        ]
        if not rows:
            return "No conditions found for that product."
        return "\n".join(f"- {p} / {item}: {fee} ({note})" for p, item, fee, note in rows)

    return [get_branch_opening_hours, list_branch_locations, get_general_conditions]
