"""Fixed, code-written replies in every supported language.

These never go through a model, so they are translated here by hand. Keys are
shared by all languages; ``text()`` falls back to the default language.
"""

from __future__ import annotations

from localization.language import DEFAULT_LANGUAGE, current_language

MESSAGES: dict[str, dict[str, str]] = {
    "failure": {
        "hu": (
            "Erre a kérdésre most nem tudok megbízható választ adni. "
            "Kérem, próbálja újra, vagy nézze meg közvetlenül a banki rendszerben."
        ),
        "en": (
            "I can't give a reliable answer to this question right now. "
            "Please try again, or check directly in the banking system."
        ),
    },
    "access_denied": {
        "hu": (
            "A kiválasztott ügyfél csomagja nem tartalmazza ezt a funkciót "
            "({menu_path}); ehhez legalább '{required_entitlement}' jogosultsági "
            "szint szükséges."
        ),
        "en": (
            "The selected customer's package does not include this feature "
            "({menu_path}); it requires at least the '{required_entitlement}' "
            "entitlement tier."
        ),
    },
    "injection_refusal": {
        "hu": (
            "Az ilyen üzenetbe ágyazott utasításokat nem követhetem. Kérem, tegyen fel "
            "egy hétköznapi kérdést a kiválasztott ügyfél számláiról, tranzakcióiról, "
            "termékeiről vagy ajánlatairól."
        ),
        "en": (
            "I can't follow instructions embedded in a message like that. Please ask "
            "a normal question about the selected customer's accounts, transactions, "
            "products, or offers."
        ),
    },
    "query_only": {
        "hu": (
            "Csak lekérdezéseket tudok végezni - nem módosítottam, nem hagytam jóvá "
            "és nem nyitottam meg semmit. A módosításokat kérem a szokásos banki "
            "rendszerekben végezze el."
        ),
        "en": (
            "I can only look up information - I have not changed, approved, or opened "
            "anything. Please action any changes through the usual banking systems."
        ),
    },
}


def text(key: str, language: str | None = None, **values: str) -> str:
    """The message ``key`` in ``language`` (default: the current turn's)."""
    variants = MESSAGES[key]
    template = variants.get(language or current_language()) or variants[DEFAULT_LANGUAGE]
    return template.format(**values) if values else template
