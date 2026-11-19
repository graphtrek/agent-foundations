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
class Loan:
    loan_id: str
    customer_id: str
    product_id: str
    name: str
    original_amount: float
    outstanding_balance: float
    monthly_payment: float
    interest_rate: float  # percent, annual
    next_payment_date: date
    maturity_date: date
    repayment_account_id: str
    currency: str = "HUF"


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

# --- Existing loans (only cust-002 has any; cust-001/003 have none) -----------

_LOANS: list[Loan] = [
    Loan("loan-002-1", "cust-002", "prod-mortgage", "Otthon Lakáshitel",
         28_000_000.0, 21_450_000.0, 220_000.0, 7.3,
         date(2026, 11, 19), date(2041, 3, 19), "acc-002-chk"),
    Loan("loan-002-2", "cust-002", "prod-loan", "Rugalmas Személyi Kölcsön",
         3_000_000.0, 2_790_000.0, 78_500.0, 11.9,
         date(2026, 11, 17), date(2030, 9, 17), "acc-002-chk"),
]

# --- Service data: business accounts, scheduled payments, cards, applications, -
# --- tickets, conditions (mirrors the mock-up-only fixtures in catalog.html) ----

@dataclass
class BusinessAccount:
    account_id: str
    customer_id: str
    account_type: str
    name: str
    balance: float
    currency: str = "HUF"


@dataclass
class ScheduledPayment:
    payment_id: str
    customer_id: str
    from_account_id: str
    beneficiary: str
    amount: float | None  # None = variable (direct debit)
    frequency: str
    next_execution: date
    status: str


@dataclass
class Card:
    card_id: str
    customer_id: str
    kind: str  # "debit" | "credit"
    brand: str
    number: str
    account_id: str
    expires: str
    status: str


@dataclass
class LoanApplication:
    application_id: str
    customer_id: str
    product_id: str
    amount: float
    history: list[tuple[str, str, str]]  # (date, status, note)


@dataclass
class SupportTicket:
    ticket_id: str
    customer_id: str
    subject: str
    history: list[tuple[str, str, str, str]]  # (time, status, by, message)


_BUSINESS_ACCOUNTS: list[BusinessAccount] = [
    BusinessAccount("acc-002-biz", "cust-002", "business_checking",
                    "Kovács Consulting Kft. - Üzleti számla", 4_250_000.0),
    BusinessAccount("acc-002-biz-payroll", "cust-002", "sub_account",
                    "Bérszámfejtési alszámla", 1_800_000.0),
    BusinessAccount("acc-002-biz-tax", "cust-002", "sub_account",
                    "Adó- és járulék alszámla", 650_000.0),
]

_SCHEDULED: list[ScheduledPayment] = [
    ScheduledPayment("sp-001-1", "cust-001", "acc-001-chk", "Lakbér - Kiss Péter", 180_000.0, "monthly (20th)", date(2026, 11, 20), "active"),
    ScheduledPayment("sp-001-2", "cust-001", "acc-001-chk", "Saját megtakarítás (acc-001-sav)", 50_000.0, "monthly (15th)", date(2026, 12, 15), "active"),
    ScheduledPayment("sp-002-1", "cust-002", "acc-002-chk", "Jelzáloghitel törlesztés", 220_000.0, "monthly (19th)", date(2026, 12, 19), "active"),
    ScheduledPayment("sp-002-2", "cust-002", "acc-002-chk", "MVM Next - csoportos beszedés", None, "monthly (direct debit)", date(2026, 11, 25), "active"),
    ScheduledPayment("sp-002-3", "cust-002", "acc-002-chk", "Iskolai tandíj", 150_000.0, "one-off", date(2026, 12, 1), "active"),
    ScheduledPayment("sp-003-1", "cust-003", "acc-003-chk", "Albérlet - Tóth Anna", 90_000.0, "monthly (14th)", date(2026, 12, 14), "active"),
    ScheduledPayment("sp-003-2", "cust-003", "acc-003-chk", "Telekom - csoportos beszedés", None, "monthly (direct debit)", date(2026, 12, 2), "paused"),
]

_CARDS: list[Card] = [
    Card("card-001-deb", "cust-001", "debit", "Visa Debit", "**** 4821", "acc-001-chk", "2028-05", "active"),
    Card("card-001-cc", "cust-001", "credit", "Mastercard Gold", "**** 7710", "-", "2027-09", "active"),
    Card("card-002-deb", "cust-002", "debit", "Visa Business Debit", "**** 1934", "acc-002-chk", "2029-01", "active"),
    Card("card-002-cc", "cust-002", "credit", "Mastercard Business", "**** 5520", "-", "2028-11", "active"),
    Card("card-002-old", "cust-002", "debit", "Visa Debit", "**** 3307", "acc-002-chk", "2027-03", "blocked (lost)"),
    Card("card-003-deb", "cust-003", "debit", "Visa Debit", "**** 6642", "acc-003-chk", "2026-12", "active"),
]

# card_id -> [(limit type, limit, used today)]
_CARD_LIMITS: dict[str, list[tuple[str, float, float]]] = {
    "card-001-deb": [("Daily purchase", 500_000, 15_990), ("Daily ATM withdrawal", 200_000, 0), ("Daily online", 300_000, 15_990)],
    "card-001-cc": [("Credit limit", 800_000, 124_300), ("Daily purchase", 400_000, 0), ("Daily ATM withdrawal", 100_000, 0)],
    "card-002-deb": [("Daily purchase", 1_000_000, 62_300), ("Daily ATM withdrawal", 400_000, 45_000), ("Daily online", 600_000, 0)],
    "card-002-cc": [("Credit limit", 2_500_000, 410_000), ("Daily purchase", 1_000_000, 0), ("Daily ATM withdrawal", 200_000, 0)],
    "card-002-old": [("Daily purchase", 0, 0), ("Daily ATM withdrawal", 0, 0), ("Daily online", 0, 0)],
    "card-003-deb": [("Daily purchase", 250_000, 3_490), ("Daily ATM withdrawal", 100_000, 0), ("Daily online", 150_000, 0)],
}

_LOAN_APPLICATIONS: list[LoanApplication] = [
    LoanApplication("la-001-1", "cust-001", "prod-mortgage", 25_000_000.0, [
        ("2026-10-28", "submitted", "Online application received."),
        ("2026-10-30", "documents_received", "Income certificate and property documents uploaded."),
        ("2026-11-06", "under_review", "Property valuation scheduled for 2026-11-24.")]),
    LoanApplication("la-002-1", "cust-002", "prod-loan", 3_000_000.0, [
        ("2026-09-12", "submitted", "Application submitted at branch-buda."),
        ("2026-09-15", "approved", "Approved at 11.9% THM, 48 months."),
        ("2026-09-17", "disbursed", "Amount credited to acc-002-chk.")]),
    LoanApplication("la-003-1", "cust-003", "prod-loan", 1_500_000.0, [
        ("2026-11-11", "submitted", "Online application received."),
        ("2026-11-13", "documents_requested", "Last 3 months' payslips requested.")]),
]

_TICKETS: list[SupportTicket] = [
    SupportTicket("tk-001-1", "cust-001", "Kártyás vásárlás reklamáció (eMAG, 15 990 Ft)", [
        ("2026-11-11 09:14", "open", "customer", "Nem ismerem fel a terhelést."),
        ("2026-11-11 13:40", "in_progress", "support", "A kártyatársaságtól bekértük a tranzakció adatait.")]),
    SupportTicket("tk-002-1", "cust-002", "Netbank belépési hiba", [
        ("2026-10-04 08:02", "open", "customer", "SMS kód nem érkezik."),
        ("2026-10-04 10:15", "resolved", "support", "Telefonszám újraregisztrálva, a belépés működik.")]),
    SupportTicket("tk-002-2", "cust-002", "Számlakivonat másolat 2026-09", [
        ("2026-11-14 16:20", "open", "customer", "Papír alapú másolatot kérek a szeptemberi kivonatról.")]),
    SupportTicket("tk-003-1", "cust-003", "Mobilszám módosítás", [
        ("2026-10-20 11:05", "open", "customer", "Új telefonszámot szeretnék megadni."),
        ("2026-10-21 09:30", "resolved", "branch-pest", "Személyes azonosítás után módosítva.")]),
]

# [product, item, fee / rate, note] - general, not customer-specific.
_CONDITIONS: list[tuple[str, str, str, str]] = [
    ("Lakossági Folyószámla", "Monthly account fee", "990 Ft", "Waived above 250 000 Ft monthly income"),
    ("Lakossági Folyószámla", "Domestic transfer (online)", "0.3%, min. 150 Ft", "First 2 transfers per month free"),
    ("Lakossági Folyószámla", "ATM withdrawal (own ATM)", "0.6% + 200 Ft", "First 2 withdrawals per month free"),
    ("Megtakarítási Számla", "Interest", "4.5% éves hozam", "Credited monthly"),
    ("Megtakarítási Számla", "Withdrawal", "0 Ft", "Up to 2 per month, then 300 Ft"),
    ("Lekötött Betét Plusz", "Interest", "5.2% éves hozam", "12-month term, fixed"),
    ("Lekötött Betét Plusz", "Early termination", "Interest forfeited", "Principal fully returned"),
    ("Mindennapi Hitelkártya", "Annual fee", "8 900 Ft", "1% cashback on grocery and fuel"),
    ("Mindennapi Hitelkártya", "THM", "24.9%", "Interest-free period up to 45 days"),
    ("Rugalmas Személyi Kölcsön", "THM", "from 11.9%", "1-10 million Ft, 12-84 months"),
    ("Otthon Lakáshitel", "THM", "from 7.3%", "Up to 30 years, property valuation 45 000 Ft"),
    ("International transfer", "SWIFT fee", "0.4%, min. 4 000 Ft", "Premium tier and above"),
]

# --- Branches and opening hours -------------------------------------------------
# Mirrors MOCK.branches / MOCK.hours in webapp_mockup/catalog.html (by hand).

@dataclass
class Branch:
    branch_id: str
    name: str
    city: str
    address: str
    postal_code: str = ""
    lat: float = 0.0
    lon: float = 0.0


_BRANCHES: list[Branch] = [
    Branch("branch-buda", "Buda Központ", "Budapest", "Attila út 12.", "1012", 47.4979, 19.0336),
    Branch("branch-pest", "Pest Belváros", "Budapest", "Váci utca 20.", "1052", 47.4935, 19.0530),
    Branch("branch-debrecen", "Debrecen Piac utca", "Debrecen", "Piac utca 30.", "4024", 47.5316, 21.6273),
    Branch("branch-szeged", "Szeged Kárász utca", "Szeged", "Kárász utca 8.", "6720", 46.2530, 20.1482),
    Branch("branch-gyor", "Győr Baross út", "Győr", "Baross Gábor út 15.", "9021", 47.6849, 17.6351),
]

# weekday index (Monday=0) -> (opens, closes, note); None = closed.
_DEFAULT_HOURS: dict[int, tuple[str, str, str] | None] = {
    0: ("08:00", "17:00", ""), 1: ("08:00", "16:00", ""), 2: ("08:00", "16:00", ""),
    3: ("08:00", "18:00", "Late opening"), 4: ("08:00", "14:00", ""), 5: None, 6: None,
}
_BRANCH_HOURS: dict[str, dict[int, tuple[str, str, str] | None]] = {
    "branch-buda": {
        0: ("08:00", "18:00", ""), 1: ("08:00", "18:00", ""), 2: ("08:00", "18:00", ""),
        3: ("08:00", "19:00", "Late opening"), 4: ("08:00", "15:00", ""),
        5: ("09:00", "12:00", "Cash desk closed"), 6: None,
    },
}
# Date-specific exceptions apply to every branch.
_HOLIDAY_EXCEPTIONS: dict[date, tuple[str, str, str] | None] = {
    date(2026, 12, 24): None,
    date(2026, 12, 31): ("08:00", "12:00", "Short day"),
}

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


def get_loans(customer_id: str) -> list[Loan]:
    """Return the customer's existing (disbursed) loans."""
    return [loan for loan in _LOANS if loan.customer_id == customer_id]


def list_branches() -> list[Branch]:
    """Return every branch."""
    return list(_BRANCHES)


def find_branch(name_or_id: str) -> Branch | None:
    """Find a branch by id or (case-insensitive) name fragment."""
    needle = name_or_id.strip().lower()
    return next(
        (b for b in _BRANCHES if needle == b.branch_id or needle in b.name.lower()
         or needle in b.branch_id),
        None,
    )


def get_branch_hours(branch_id: str, day: date) -> tuple[str, str, str] | None:
    """Return (opens, closes, note) for the branch on that date, None if closed.

    Holiday exceptions override the weekly schedule; a branch without its own
    schedule uses the default one.
    """
    if day in _HOLIDAY_EXCEPTIONS:
        return _HOLIDAY_EXCEPTIONS[day]
    schedule = _BRANCH_HOURS.get(branch_id, _DEFAULT_HOURS)
    return schedule[day.weekday()]


def get_account(customer_id: str, account_id: str) -> Account | None:
    """Return one of the customer's own accounts, or None."""
    return next((a for a in get_accounts(customer_id) if a.account_id == account_id), None)


def get_business_accounts(customer_id: str) -> list[BusinessAccount]:
    """Return the customer's business accounts and sub-accounts."""
    return [a for a in _BUSINESS_ACCOUNTS if a.customer_id == customer_id]


def get_scheduled_payments(customer_id: str) -> list[ScheduledPayment]:
    return [p for p in _SCHEDULED if p.customer_id == customer_id]


def get_cards(customer_id: str) -> list[Card]:
    return [c for c in _CARDS if c.customer_id == customer_id]


def get_card_limits(customer_id: str, card_id: str) -> list[tuple[str, float, float]] | None:
    """Limits of one of the customer's own cards, or None if not theirs."""
    if not any(c.card_id == card_id for c in get_cards(customer_id)):
        return None
    return list(_CARD_LIMITS.get(card_id, []))


def get_loan_applications(customer_id: str) -> list[LoanApplication]:
    return [a for a in _LOAN_APPLICATIONS if a.customer_id == customer_id]


def get_support_tickets(customer_id: str) -> list[SupportTicket]:
    return [t for t in _TICKETS if t.customer_id == customer_id]


def list_conditions() -> list[tuple[str, str, str, str]]:
    return list(_CONDITIONS)
