"""Registry of the customer-scoped tool groups an architecture profile can use."""

from typing import Any

from tools.account_tools import create_account_specialist_tools
from tools.product_tools import create_product_specialist_tools
from tools.public_info_tools import create_public_info_tools
from tools.service_tools import create_service_specialist_tools
from tools.web_tools import create_page_reader_tools

# Groups a profile can hand to a specialist (or, in ``flat`` mode, to the
# coordinator itself). Each builder takes a customer id.
TOOL_GROUPS: dict[str, Any] = {
    "account": create_account_specialist_tools,
    "product": create_product_specialist_tools,
    "service": create_service_specialist_tools,
    "public": create_public_info_tools,
    "web": create_page_reader_tools,
}

# Groups whose tools answer the same for everyone: their specialist needs no
# selected customer, and in ``flat`` mode they are the coordinator's direct tools.
CUSTOMER_FREE_GROUPS = frozenset({"public", "web"})

DIRECT_TOOL_NAMES = (
    "list_customers",
    "select_customer",
    "get_branch_opening_hours",
    "list_branch_locations",
    "get_general_conditions",
)

# Endpoint categories each tool group serves (for the router hint).
GROUP_CATEGORIES: dict[str, tuple[str, ...]] = {
    "account": ("accounts", "payments"),
    "product": ("loans",),
    "service": ("cards", "profile", "support"),
    "public": ("general",),
    "web": (),
}


def group_tool_names(group: str) -> tuple[str, ...]:
    """Names of the tools in one group (the dummy customer id is never used:
    the tools only close over it)."""
    return tuple(t.name for t in TOOL_GROUPS[group](""))
