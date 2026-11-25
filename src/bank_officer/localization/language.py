"""Supported reply languages, deterministic language detection and the
per-turn "current language" that code-level replies and guardrails read.

Detection is plain code (no model call, no dependency): it must be cheap,
work offline and be testable. The officer can override it with the language
selector (``"auto"`` means detect on every message).
"""

from __future__ import annotations

import re
from contextvars import ContextVar

SUPPORTED = ("en", "hu")
AUTO = "auto"
DEFAULT_LANGUAGE = "hu"
LANGUAGE_NAMES = {"en": "English", "hu": "Magyar"}

_HU_WORDS = frozenset(
    """a az és vagy nem igen egy mi mit mikor hol hogyan melyik mennyi mennyit mennyire kik ki
    van volt lesz vannak voltak szeretném szeretnék kérem kérek legyen jelenleg
    ügyfél ügyfélnek ügyfelet számla számlája számlái számlák egyenleg egyenlege tranzakció
    tranzakciók átutalás átutalások hitel hitele hitelei kártya kártyák kártyái limit limitek
    ajánlat ajánlatai termék termékek nyitva nyitvatartás nyitvatartása fiók fiókok
    költés költött költöttem költése kimenő bejövő utolsó utolsó legutóbbi jövő múlt
    holnap ma tegnap hétfő kedd szerda csütörtök péntek szombat vasárnap hét hónap év
    köszönöm szia szép napot jó reggelt válaszd ki mutasd foglald össze milyen jogosult
    ezt azt ezen azon és meg el be ki fel le is csak még már nekem neki alapján után között
    van-e nincs több legtöbb""".split()
)
_EN_WORDS = frozenset(
    """the a an and or not yes is are was were be been has have had do does did what when where
    how which who why whose whom much many show tell give list select choose summarize summarise
    please can could would should may might will shall i we you he she it they me my our your
    his her its their this that these those of to in on at for from with by about between
    account accounts balance balances customer customers transaction transactions transfer
    transfers loan loans card cards limit limits offer offers product products opening hours
    open branch branches last next month week year today tomorrow yesterday monday tuesday
    wednesday thursday friday saturday sunday spent spend spending incoming outgoing recent
    latest there any all if then than also only still already after before since over under
    does eligible entitled status ticket tickets support fee fees""".split()
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
# English look-alikes that are also Hungarian words ("a", "is", "or", "ma").
_AMBIGUOUS = frozenset({"a", "is", "or", "not", "do", "he", "me", "in", "on", "at", "it", "for", "ma", "meg", "el", "be", "ki", "fel", "le"})

# The language of the turn being processed. Set by ``BranchSession`` before the
# pipeline runs; LangGraph copies the context into its worker threads, so tools
# and middleware can read it without it travelling through graph state.
_current: ContextVar[str] = ContextVar("bank_officer_language", default=DEFAULT_LANGUAGE)


def normalize(language: str | None) -> str:
    """``"auto"`` or a supported code; anything else counts as ``"auto"``."""
    value = (language or AUTO).strip().lower()[:2]
    return value if value in SUPPORTED else AUTO


def detect_language(text: str, fallback: str = DEFAULT_LANGUAGE) -> str:
    """Guess ``"en"`` or ``"hu"`` from ``text``; ``fallback`` on a tie (a bare
    name, a number, a one-word greeting) so the conversation keeps its language."""
    hu = en = 0
    for word in _WORD.findall(text.lower()):
        in_hu, in_en = word in _HU_WORDS, word in _EN_WORDS
        if word in _AMBIGUOUS:
            continue
        if in_hu:
            hu += 1
        if in_en:
            en += 1
    if hu == en:
        return fallback if fallback in SUPPORTED else DEFAULT_LANGUAGE
    return "hu" if hu > en else "en"


def resolve_language(selected: str | None, text: str, previous: str | None = None) -> str:
    """The language for one turn: the selector's choice, or - on ``auto`` -
    what ``text`` looks like, keeping ``previous`` when it is inconclusive."""
    choice = normalize(selected)
    if choice != AUTO:
        return choice
    return detect_language(text, fallback=previous or DEFAULT_LANGUAGE)


def set_current_language(language: str) -> None:
    _current.set(language if language in SUPPORTED else DEFAULT_LANGUAGE)


def current_language() -> str:
    return _current.get()
