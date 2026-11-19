"""Static mock bank data for the branch officer assistant demo.

No network access, no external services - just in-memory fixtures and pure
lookup functions, mirroring the "no business logic in the runnable script"
split used by ``offsite_images.py``, but without any download/caching step
since this data is fully synthetic.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

EntitlementTier = Literal["retail", "premium", "business"]


@dataclass
class Customer:
    customer_id: str
    full_name: str
    date_of_birth: date
    phone: str
    email: str
    home_branch_id: str
    entitlement_tier: EntitlementTier = "retail"


@dataclass
class Account:
    account_id: str
    customer_id: str
    account_type: str  # "checking" | "savings"
    product_name: str
    balance: float
    opened_on: date
    currency: str = "HUF"


@dataclass
class Transaction:
    transaction_id: str
    account_id: str
    booking_date: date
    amount: float  # positive = credit, negative = debit
    description: str
    category: str
    currency: str = "HUF"
    counterparty: str | None = None  # remitter (credit) / payee (debit)
    reference: str | None = None  # "közlemény" (payment message)


@dataclass
class Product:
    product_id: str
    name: str
    category: str  # "savings" | "loan" | "credit_card" | "deposit" | "mortgage"
    description: str
    rate_label: str  # e.g. "THM" or "eves hozam"
    headline_rate: float  # percent


@dataclass
class Offer:
    offer_id: str
    customer_id: str
    product_id: str
    description: str
    discount_detail: str
    valid_until: date
    reason: str


# --- Customers -------------------------------------------------------------

_CUSTOMERS: list[Customer] = [
    Customer(
        customer_id="cust-001",
        full_name="Nagy Katalin",
        date_of_birth=date(1985, 4, 12),
        phone="+36 20 123 4567",
        email="nagy.katalin@example.hu",
        home_branch_id="branch-buda",
        entitlement_tier="premium",
    ),
    Customer(
        customer_id="cust-002",
        full_name="Kovács Bence",
        date_of_birth=date(1979, 11, 3),
        phone="+36 30 234 5678",
        email="kovacs.bence@example.hu",
        home_branch_id="branch-buda",
        entitlement_tier="business",
    ),
    Customer(
        customer_id="cust-003",
        full_name="Szabó Emese",
        date_of_birth=date(1992, 7, 21),
        phone="+36 70 345 6789",
        email="szabo.emese@example.hu",
        home_branch_id="branch-pest",
        entitlement_tier="retail",
    ),
]

# --- Accounts ----------------------------------------------------------------

_ACCOUNTS: list[Account] = [
    Account("acc-001-chk", "cust-001", "checking", "Lakossági Folyószámla",
            482_350.0, date(2016, 3, 1)),
    Account("acc-001-sav", "cust-001", "savings", "Megtakarítási Számla",
            3_120_000.0, date(2018, 9, 15)),
    Account("acc-002-chk", "cust-002", "checking", "Lakossági Folyószámla",
            915_420.0, date(2011, 6, 20)),
    Account("acc-002-sav", "cust-002", "savings", "Megtakarítási Számla",
            7_480_000.0, date(2012, 1, 10)),
    Account("acc-003-chk", "cust-003", "checking", "Lakossági Folyószámla",
            168_900.0, date(2021, 2, 5)),
    Account("acc-003-sav", "cust-003", "savings", "Megtakarítási Számla",
            540_000.0, date(2021, 2, 5)),
]

# --- Transactions --------------------------------------------------------------
# (booking_date, amount, description, category) per account, oldest-first.

_TXN_ROWS: dict[str, list[tuple[str, float, str, str]]] = {
    "acc-001-chk": [
        ("2026-09-18", 450_000.0, "Munkabér - ACME Zrt.", "salary"),
        ("2026-09-20", -180_000.0, "Lakbér átutalás", "rent"),
        ("2026-09-24", -12_450.0, "Tesco vásárlás", "grocery"),
        ("2026-10-02", -6_990.0, "Netflix előfizetés", "subscription"),
        ("2026-10-05", -20_000.0, "ATM készpénzfelvétel", "atm_withdrawal"),
        ("2026-10-18", 450_000.0, "Munkabér - ACME Zrt.", "salary"),
        ("2026-10-22", -18_200.0, "MVM közműszámla", "utility"),
        ("2026-11-01", -8_450.0, "Belvárosi étterem", "restaurant"),
        ("2026-11-10", -15_990.0, "Online vásárlás - eMAG", "shopping"),
    ],
    "acc-001-sav": [
        ("2026-08-15", 500_000.0, "Átvezetés folyószámláról", "transfer_in"),
        ("2026-09-01", 3_120.0, "Kamatjóváírás", "interest"),
        ("2026-09-30", 3_125.0, "Kamatjóváírás", "interest"),
        ("2026-10-10", 300_000.0, "Átvezetés folyószámláról", "transfer_in"),
        ("2026-10-31", 3_250.0, "Kamatjóváírás", "interest"),
        ("2026-11-05", -100_000.0, "Átvezetés folyószámlára", "transfer_out"),
        ("2026-11-14", 100_000.0, "Készpénz befizetés", "deposit"),
        ("2026-11-14", 3_300.0, "Kamatjóváírás", "interest"),
        ("2026-11-15", 50_000.0, "Átvezetés folyószámláról", "transfer_in"),
    ],
    "acc-002-chk": [
        ("2026-09-15", 780_000.0, "Munkabér - DeltaTech Kft.", "salary"),
        ("2026-09-19", -220_000.0, "Jelzáloghitel törlesztés", "loan_payment"),
        ("2026-09-27", -34_900.0, "Benzinkút - MOL", "fuel"),
        ("2026-10-03", -9_990.0, "Spotify + HBO Max", "subscription"),
        ("2026-10-15", 780_000.0, "Munkabér - DeltaTech Kft.", "salary"),
        ("2026-10-19", -220_000.0, "Jelzáloghitel törlesztés", "loan_payment"),
        ("2026-10-28", -45_000.0, "ATM készpénzfelvétel", "atm_withdrawal"),
        ("2026-11-05", -62_300.0, "Auchan vásárlás", "grocery"),
        ("2026-11-12", -14_500.0, "Gyógyszertár", "health"),
    ],
    "acc-002-sav": [
        ("2026-08-01", 1_000_000.0, "Lekötött betét lejárat - jóváírás", "deposit_maturity"),
        ("2026-09-01", 28_600.0, "Kamatjóváírás", "interest"),
        ("2026-09-20", 500_000.0, "Átvezetés folyószámláról", "transfer_in"),
        ("2026-10-01", 30_100.0, "Kamatjóváírás", "interest"),
        ("2026-10-15", -1_200_000.0, "Lekötött betétbe helyezés", "deposit_placement"),
        ("2026-11-01", 29_800.0, "Kamatjóváírás", "interest"),
        ("2026-11-08", 200_000.0, "Átvezetés folyószámláról", "transfer_in"),
        ("2026-11-14", 31_200.0, "Kamatjóváírás", "interest"),
        ("2026-11-15", 15_000.0, "Osztalékjóváírás", "dividend"),
    ],
    "acc-003-chk": [
        ("2026-09-10", 310_000.0, "Munkabér - StartUpHub Kft.", "salary"),
        ("2026-09-14", -90_000.0, "Albérlet átutalás", "rent"),
        ("2026-09-22", -9_450.0, "Lidl vásárlás", "grocery"),
        ("2026-10-02", -4_990.0, "Telekom mobilszámla", "utility"),
        ("2026-10-10", 310_000.0, "Munkabér - StartUpHub Kft.", "salary"),
        ("2026-10-16", -25_000.0, "ATM készpénzfelvétel", "atm_withdrawal"),
        ("2026-10-29", -11_990.0, "Online vásárlás - ASOS", "shopping"),
        ("2026-11-04", -7_200.0, "Kávézó", "restaurant"),
        ("2026-11-13", -3_490.0, "Bolt vásárlás", "grocery"),
    ],
    "acc-003-sav": [
        ("2026-09-01", 100_000.0, "Készpénz befizetés", "deposit"),
        ("2026-09-15", 300.0, "Kamatjóváírás", "interest"),
        ("2026-10-01", 500.0, "Kamatjóváírás", "interest"),
        ("2026-10-12", 150_000.0, "Átvezetés folyószámláról", "transfer_in"),
        ("2026-10-15", 700.0, "Kamatjóváírás", "interest"),
        ("2026-11-01", 900.0, "Kamatjóváírás", "interest"),
        ("2026-11-05", -50_000.0, "Átvezetés folyószámlára", "transfer_out"),
        ("2026-11-10", 288_600.0, "Hozamkifizetés", "interest"),
        ("2026-11-14", 1_000.0, "Kamatjóváírás", "interest"),
    ],
}

# Counterparty and reference ("közlemény") for selected transactions, keyed by
# (account_id, booking_date, amount).
_TXN_DETAILS: dict[tuple[str, str, float], tuple[str, str]] = {
    ("acc-001-chk", "2026-09-18", 450_000.0): ("ACME Zrt.", "Szeptemberi munkabér"),
    ("acc-001-chk", "2026-10-18", 450_000.0): ("ACME Zrt.", "Októberi munkabér"),
    ("acc-001-sav", "2026-11-15", 50_000.0): ("Kovács János", "Saját számlák közötti átvezetés"),
    ("acc-002-chk", "2026-09-15", 780_000.0): ("DeltaTech Kft.", "Szeptemberi munkabér"),
    ("acc-002-chk", "2026-10-15", 780_000.0): ("DeltaTech Kft.", "Októberi munkabér"),
    ("acc-002-sav", "2026-11-15", 15_000.0): ("Alfa Befektetési Alap", "2026. évi osztalék"),
    ("acc-003-chk", "2026-09-10", 310_000.0): ("StartUpHub Kft.", "Szeptemberi munkabér"),
    ("acc-003-chk", "2026-10-10", 310_000.0): ("StartUpHub Kft.", "Októberi munkabér"),
    ("acc-003-sav", "2026-11-10", 288_600.0): ("Béta Vagyonkezelő Zrt.", "Hozamkifizetés Q3"),
}

_TRANSACTIONS: list[Transaction] = [
    Transaction(
        f"txn-{account_id[4:]}-{index:02d}",
        account_id,
        date.fromisoformat(booking_date),
        amount,
        description,
        category,
        counterparty=_TXN_DETAILS.get((account_id, booking_date, amount), (None, None))[0],
        reference=_TXN_DETAILS.get((account_id, booking_date, amount), (None, None))[1],
    )
    for account_id, rows in _TXN_ROWS.items()
    for index, (booking_date, amount, description, category) in enumerate(rows, start=1)
]

# --- Product catalog (shared across customers) -------------------------------

_PRODUCTS: list[Product] = [
    Product("prod-savings", "Zöld Megtakarítási Számla", "savings",
            "Rugalmas, azonnal elérhető megtakarítási számla kamatjóváírással havonta.",
            "éves hozam", 4.5),
    Product("prod-loan", "Rugalmas Személyi Kölcsön", "loan",
            "Fedezet nélküli személyi kölcsön akár 10 millió Ft összegben, "
            "12-84 hónapos futamidőre.",
            "THM", 11.9),
    Product("prod-creditcard", "Mindennapi Hitelkártya", "credit_card",
            "Hitelkártya 1% visszatérítéssel élelmiszer- és üzemanyag-vásárlásra.",
            "THM", 24.9),
    Product("prod-deposit", "Lekötött Betét Plusz", "deposit",
            "12 hónapos lekötött betét garantált hozammal.",
            "éves hozam", 5.2),
    Product("prod-mortgage", "Otthon Lakáshitel", "mortgage",
            "Jelzáloghitel lakásvásárlásra vagy felújításra, akár 30 éves futamidővel.",
            "THM", 7.3),
]

# --- Personalized offers -------------------------------------------------------

_OFFERS: list[Offer] = [
    Offer("offer-001a", "cust-001", "prod-deposit",
          "Exkluzív THM-kedvezmény a Lekötött Betét Pluszra.",
          "+0.5 pp hozam az első 12 hónapban",
          date(2026, 12, 31),
          "A megtakarítási számla egyenlege meghaladja a 3 millió Ft-ot."),
    Offer("offer-001b", "cust-001", "prod-creditcard",
          "Díjmentes első év a Mindennapi Hitelkártyánál.",
          "Éves díj elengedve az első 12 hónapban",
          date(2027, 1, 31),
          "Rendszeres havi jövedelem érkezik a folyószámlára."),
    Offer("offer-002a", "cust-002", "prod-mortgage",
          "Kedvezményes THM az Otthon Lakáshitelre.",
          "-0.4 pp a hirdetett THM-ből a teljes futamidőre",
          date(2027, 2, 28),
          "Meglévő jelzáloghitel korai kiváltása esetén."),
    Offer("offer-002b", "cust-002", "prod-deposit",
          "Prémium lekötési ajánlat a Lekötött Betét Pluszra.",
          "+0.6 pp hozam 2 millió Ft feletti lekötésre",
          date(2026, 12, 15),
          "A megtakarítási számla egyenlege meghaladja a 5 millió Ft-ot."),
    Offer("offer-003a", "cust-003", "prod-loan",
          "Gyorsított elbírálású Rugalmas Személyi Kölcsön.",
          "-1.0 pp a hirdetett THM-ből 36 hónapos futamidőig",
          date(2027, 1, 15),
          "Fiatal, stabil jövedelmű ügyfél kedvezményes célcsoportja."),
    Offer("offer-003b", "cust-003", "prod-savings",
          "Induló megtakarítási bónusz a Zöld Megtakarítási Számlára.",
          "+0.3 pp hozam az első 6 hónapban",
          date(2027, 3, 31),
          "Rendszeres havi megtakarítás az elmúlt 3 hónapban."),
]


# --- Lookup functions ----------------------------------------------------------

def list_customers() -> list[Customer]:
    """Return every customer available in this demo branch session."""
    return list(_CUSTOMERS)


def find_customer(name_or_id: str) -> Customer | None:
    """Find a customer by exact id or case-insensitive name substring."""
    needle = name_or_id.strip().lower()
    for customer in _CUSTOMERS:
        if customer.customer_id.lower() == needle:
            return customer
    for customer in _CUSTOMERS:
        if needle in customer.full_name.lower():
            return customer
    return None


def get_accounts(customer_id: str) -> list[Account]:
    """Return all accounts owned by the given customer."""
    return [account for account in _ACCOUNTS if account.customer_id == customer_id]


def get_transactions(
    account_id: str,
    *,
    min_amount: float | None = None,
    since: date | None = None,
) -> list[Transaction]:
    """Return transactions for an account, newest first, with optional filters."""
    results = [t for t in _TRANSACTIONS if t.account_id == account_id]
    if min_amount is not None:
        results = [t for t in results if abs(t.amount) >= min_amount]
    if since is not None:
        results = [t for t in results if t.booking_date >= since]
    return sorted(results, key=lambda t: t.booking_date, reverse=True)


def list_products() -> list[Product]:
    """Return the shared product catalog."""
    return list(_PRODUCTS)


def get_product(product_id: str) -> Product | None:
    """Look up a single product by id."""
    return next((p for p in _PRODUCTS if p.product_id == product_id), None)


def get_offers(customer_id: str) -> list[Offer]:
    """Return personalized offers for the given customer."""
    return [offer for offer in _OFFERS if offer.customer_id == customer_id]
