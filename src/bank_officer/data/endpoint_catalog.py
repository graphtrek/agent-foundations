"""Static mock REST endpoint catalog for a web banking application.

Same "no business logic outside this module" split as ``bank_data.py``: just
in-memory fixtures and pure lookup/search functions. Mirrored for visual
reference in ``src/bank_officer/webapp_mockup/catalog.html`` — keep that file's
menu listing in sync by hand when this catalog changes.
"""

from dataclasses import dataclass

from data.bank_data import EntitlementTier


@dataclass
class Endpoint:
    endpoint_id: str
    method: str  # "GET" | "POST" | "PATCH" | "DELETE"
    path: str
    description: str
    category: str  # "accounts" | "payments" | "cards" | "loans" | "profile" | "support" | "general"
    menu_path: str
    required_entitlement: EntitlementTier = "retail"


_ENDPOINTS: list[Endpoint] = [
    # --- Accounts / transactions --------------------------------------------
    Endpoint("ep-accounts-list", "GET", "/accounts",
             "List the current customer's accounts with type and balance.",
             "accounts", "Accounts > Overview"),
    Endpoint("ep-accounts-get", "GET", "/accounts/{id}",
             "Get the details of a single account.",
             "accounts", "Accounts > Overview > Account details"),
    Endpoint("ep-accounts-transactions", "GET", "/accounts/{id}/transactions",
             "List recent transactions for one account, with amount/date filters.",
             "accounts", "Accounts > Transactions > Search"),
    Endpoint("ep-accounts-dispute", "POST", "/accounts/{id}/transactions/{txn_id}/dispute",
             "File a dispute on a single transaction.",
             "accounts", "Accounts > Transactions > Dispute a charge"),
    Endpoint("ep-accounts-statement", "GET", "/accounts/{id}/statements/{period}",
             "Download a monthly account statement.",
             "accounts", "Accounts > Statements"),
    Endpoint("ep-accounts-business-overview", "GET", "/accounts/business/overview",
             "View a consolidated overview of all business accounts and sub-accounts.",
             "accounts", "Accounts > Business > Consolidated overview",
             required_entitlement="business"),
    # --- Payments -------------------------------------------------------------
    Endpoint("ep-payments-transfer", "POST", "/payments/transfer",
             "Make a domestic transfer between the customer's own or saved accounts.",
             "payments", "Payments > Transfer money"),
    Endpoint("ep-payments-utility", "POST", "/payments/utility-bill",
             "Pay a utility bill by biller code and reference number.",
             "payments", "Payments > Pay a bill"),
    Endpoint("ep-payments-external", "POST", "/payments/external-transfer",
             "Send an international or external-bank wire transfer.",
             "payments", "Payments > International transfer",
             required_entitlement="premium"),
    Endpoint("ep-payments-batch", "POST", "/payments/batch",
             "Upload a batch payment file, e.g. monthly payroll.",
             "payments", "Payments > Batch / payroll upload",
             required_entitlement="business"),
    Endpoint("ep-payments-scheduled-list", "GET", "/payments/scheduled",
             "List scheduled and recurring payments.",
             "payments", "Payments > Scheduled payments"),
    Endpoint("ep-payments-scheduled-cancel", "DELETE", "/payments/scheduled/{id}",
             "Cancel a scheduled or recurring payment.",
             "payments", "Payments > Scheduled payments > Cancel"),
    # --- Cards ------------------------------------------------------------------
    Endpoint("ep-cards-list", "GET", "/cards",
             "List the customer's debit and credit cards.",
             "cards", "Cards > Overview"),
    Endpoint("ep-cards-block", "POST", "/cards/{id}/block",
             "Block a lost or stolen card.",
             "cards", "Cards > Overview > Block card"),
    Endpoint("ep-cards-unblock", "POST", "/cards/{id}/unblock",
             "Unblock a previously blocked card.",
             "cards", "Cards > Overview > Unblock card"),
    Endpoint("ep-cards-get-limits", "GET", "/cards/{id}/limits",
             "View a card's current daily spending and withdrawal limit.",
             "cards", "Cards > Overview > View limits",
             required_entitlement="premium"),
    Endpoint("ep-cards-limits", "PATCH", "/cards/{id}/limits",
             "Raise or lower a card's daily spending/withdrawal limit.",
             "cards", "Cards > Overview > Change limits",
             required_entitlement="premium"),
    # --- Loans --------------------------------------------------------------
    Endpoint("ep-loans-offers", "GET", "/loans/offers",
             "List the loan products and headline rates available to the customer.",
             "loans", "Loans > Offers"),
    Endpoint("ep-loans-list", "GET", "/loans",
             "List the customer's existing loans with balance, installment and maturity.",
             "loans", "Loans > My loans"),
    Endpoint("ep-loans-status", "GET", "/loans/applications/{id}/status",
             "Check the status of a submitted loan application.",
             "loans", "Loans > My applications > Status"),
    Endpoint("ep-loans-apply", "POST", "/loans/applications",
             "Submit a new personal loan or mortgage application.",
             "loans", "Loans > Apply",
             required_entitlement="premium"),
    Endpoint("ep-loans-business-credit-line", "POST", "/loans/business/credit-line",
             "Apply for a revolving business credit line.",
             "loans", "Loans > Business > Credit line",
             required_entitlement="business"),
    # --- Profile / support -----------------------------------------------------
    Endpoint("ep-profile-get", "GET", "/profile",
             "Get the customer's profile and contact information.",
             "profile", "Profile > My details"),
    Endpoint("ep-profile-contact", "PATCH", "/profile/contact-info",
             "Update the customer's phone number or email address.",
             "profile", "Profile > My details > Edit contact info"),
    Endpoint("ep-support-ticket-create", "POST", "/support/tickets",
             "Open a new customer support ticket.",
             "support", "Support > New request"),
    Endpoint("ep-support-ticket-status", "GET", "/support/tickets/{id}",
             "Check the status of an existing support ticket.",
             "support", "Support > My requests"),
    # --- General / smalltalk --------------------------------------------------
    Endpoint("ep-general-conditions", "GET", "/general/conditions",
             "List standard account and product terms, fees, and interest conditions.",
             "general", "General > Terms & conditions"),
    Endpoint("ep-general-branches", "GET", "/general/branches",
             "List branch locations with address and map coordinates, optionally filtered by city or postal code.",
             "general", "General > Branch locator"),
    Endpoint("ep-general-branch-hours", "GET", "/general/branches/{id}/hours",
             "Get a branch's opening hours for the week, including holiday exceptions.",
             "general", "General > Branch locator > Opening hours"),
]


def list_endpoints() -> list[Endpoint]:
    """Return every endpoint in the catalog."""
    return list(_ENDPOINTS)


def get_endpoint(endpoint_id: str) -> Endpoint | None:
    """Look up a single endpoint by id."""
    return next((e for e in _ENDPOINTS if e.endpoint_id == endpoint_id), None)


def search_endpoints(query: str) -> list[Endpoint]:
    """Return endpoints matching the query, best keyword overlap first.

    Deterministic scoring (tokenize + count overlaps against description,
    category, path, and menu_path) rather than embeddings/ML, matching the
    simple substring-matching style of ``bank_data.find_customer``.
    """
    tokens = {t for t in query.lower().split() if len(t) > 2}
    if not tokens:
        return []
    scored: list[tuple[int, Endpoint]] = []
    for endpoint in _ENDPOINTS:
        haystack = " ".join(
            (endpoint.description, endpoint.category, endpoint.path, endpoint.menu_path)
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if score > 0:
            scored.append((score, endpoint))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [endpoint for _, endpoint in scored]
