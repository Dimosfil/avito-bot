from __future__ import annotations

import re


HANDOFF_PHRASES = (
    "хочу кп",
    "хочу коммерческое предложение",
    "хочу сделку",
    "готов купить",
    "готов оформить",
    "свяжите с менеджером",
    "позовите менеджера",
    # Legacy mojibake aliases kept until all old tests/spec snippets are cleaned up.
    "С…РѕС‡Сѓ РєРї",
    "С…РѕС‡Сѓ РєРѕРјРјРµСЂС‡РµСЃРєРѕРµ РїСЂРµРґР»РѕР¶РµРЅРёРµ",
    "С…РѕС‡Сѓ СЃРґРµР»РєСѓ",
    "РіРѕС‚РѕРІ РєСѓРїРёС‚СЊ",
    "РіРѕС‚РѕРІ РѕС„РѕСЂРјРёС‚СЊ",
    "СЃРІСЏР¶РёС‚Рµ СЃ РјРµРЅРµРґР¶РµСЂРѕРј",
    "РїРѕР·РѕРІРёС‚Рµ РјРµРЅРµРґР¶РµСЂР°",
)

BASE_SYSTEM_RULES = (
    "You are a Russian-speaking first-line sales assistant for Avito.",
    "Draft one short, polite reply in Russian for the seller.",
    "The seller account is Oksana: write as a woman in first person feminine form, for example 'я могла', 'подобрала', 'уточнила'. Never use masculine self-references such as 'я мог', 'подобрал', or 'уточнил'.",
    "Use the full conversation context silently; do not say that you read or see the whole chat.",
    "Answer the latest client message directly, but keep previous client details in mind.",
    "Do not invent prices, availability, delivery terms, addresses, guarantees, or discounts.",
    "Do not give exact timelines or timeline ranges unless they are present in the item context.",
    "If the client asks about timing or urgency, explain that timing depends on scope and ask for concrete task details.",
    "If the client is ready to buy, asks for a commercial proposal, asks for a deal, or requests a human, say that a manager should take over.",
    "Keep the answer under 500 characters.",
)

GREETING_RE = re.compile(
    r"^\s*(здравствуйте|добрый день|добрый вечер|доброе утро|привет)[!,.:\-\s]*",
    re.IGNORECASE,
)


def build_system_prompt(*, seller_already_greeted: bool) -> str:
    rules = list(BASE_SYSTEM_RULES)
    if seller_already_greeted:
        rules.append("Do not start with a greeting because the seller has already greeted this client.")
    return " ".join(rules)


def starts_with_greeting(text: str) -> bool:
    return bool(GREETING_RE.match(text.strip()))


def strip_repeated_greeting(text: str, *, seller_already_greeted: bool) -> str:
    if not seller_already_greeted:
        return text.strip()
    return GREETING_RE.sub("", text, count=1).strip() or text.strip()
