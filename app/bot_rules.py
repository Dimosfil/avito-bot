from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any


DEFAULT_RULES_PATH = Path(__file__).with_name("rules") / "bot-rules.json"
RULES_PATH_ENV = "AVITO_BOT_RULES_PATH"
DEFAULT_HANDOFF_CLIENT_REPLY = (
    "✅ Приняла ваш запрос.\n\n"
    "📋 Передам информацию менеджеру — он свяжется с вами для уточнения деталей."
)


@dataclass(frozen=True)
class PromptRules:
    base_system_rules: tuple[str, ...]
    seller_already_greeted_rule: str


@dataclass(frozen=True)
class DialogueGuidanceRules:
    manager_mention_terms: tuple[str, ...]
    manager_mention_threshold: int
    detail_signal_threshold: int
    handoff_client_reply: str
    base_rules: tuple[str, ...]
    known_price_rule: str
    price_question_rule: str
    timing_question_rule: str
    repeated_manager_rule: str
    enough_details_rule: str


@dataclass(frozen=True)
class PostProcessingRules:
    greeting_re: re.Pattern[str]
    seller_name_address_re: re.Pattern[str]
    client_name_passthrough: frozenset[str]
    first_marker: str
    middle_marker: str
    last_marker: str
    single_marker: str
    bullet_marker: str
    min_inline_list_items: int


@dataclass(frozen=True)
class BotRules:
    admin_code: str
    admin_command_reason: str
    admin_mode_rules: tuple[str, ...]
    admin_dialogue_guidance: str
    admin_mode_disable_re: re.Pattern[str]
    price_question_re: re.Pattern[str]
    timing_question_re: re.Pattern[str]
    detail_signal_re: re.Pattern[str]
    buying_intent_re: re.Pattern[str]
    handoff_phrases: tuple[str, ...]
    prompt: PromptRules
    post_processing: PostProcessingRules
    dialogue_guidance: DialogueGuidanceRules


MARKDOWN_EMPHASIS_RE = re.compile(r"(?<!\*)\*\*([^*\n]+?)\*\*(?!\*)|(?<!_)__([^_\n]+?)__(?!_)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+?)`")
MARKDOWN_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ0-9])")
EMOJI_PREFIX_RE = re.compile(r"^[\u2600-\u27bf\U0001f300-\U0001faff]")
INLINE_LIST_SEPARATOR_RE = re.compile(r",\s*|\s+(?:или|и)\s+", re.IGNORECASE)
FEMININE_SELF_REFERENCE_REPLACEMENTS = (
    (re.compile(r"\b([Яя]\s+)готов\b"), r"\1готова"),
    (re.compile(r"\b([Ии]\s+)готов\b"), r"\1готова"),
    (re.compile(r"(?m)(^|[.!?]\s+)Готов\b"), r"\1Готова"),
    (re.compile(r"(?m)(^|[.!?]\s+)готов\b"), r"\1готова"),
    (re.compile(r"\b([Яя]\s+)мог\b"), r"\1могла"),
    (re.compile(r"\b([Яя]\s+)подобрал\b"), r"\1подобрала"),
    (re.compile(r"\b([Яя]\s+)уточнил\b"), r"\1уточнила"),
)
OUTGOING_TEXT_TRANSLATION = str.maketrans(
    {
        "\ufeff": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u2030": " ",
        "\ufffd": " ",
    }
)


def load_bot_rules(path: Path | str | None = None) -> BotRules:
    rules_path = Path(path) if path is not None else _configured_rules_path()
    data = _read_rules_json(rules_path)
    admin = _required_dict(data, "admin", rules_path)
    intent_patterns = _required_dict(data, "intent_patterns", rules_path)
    prompt = _required_dict(data, "prompt", rules_path)
    post_processing = _required_dict(data, "post_processing", rules_path)
    reply_formatting = post_processing.get("reply_formatting") or {}
    if not isinstance(reply_formatting, dict):
        raise RuntimeError(f"Bot rules config at {rules_path} must define object 'post_processing.reply_formatting'")
    dialogue_guidance = _required_dict(data, "dialogue_guidance", rules_path)

    admin_code = _env_override(admin.get("code_env"), _required_str(admin, "code", rules_path))
    return BotRules(
        admin_code=admin_code,
        admin_command_reason=_required_str(admin, "command_reason", rules_path),
        admin_mode_rules=_required_str_tuple(admin, "mode_rules", rules_path),
        admin_dialogue_guidance=_required_str(admin, "dialogue_guidance", rules_path),
        admin_mode_disable_re=_compile_pattern(_required_str(admin, "disable_pattern", rules_path), "admin.disable_pattern", rules_path),
        price_question_re=_compile_pattern(
            _required_str(intent_patterns, "price_question", rules_path),
            "intent_patterns.price_question",
            rules_path,
        ),
        timing_question_re=_compile_pattern(
            _required_str(intent_patterns, "timing_question", rules_path),
            "intent_patterns.timing_question",
            rules_path,
        ),
        detail_signal_re=_compile_pattern(
            _required_str(intent_patterns, "detail_signal", rules_path),
            "intent_patterns.detail_signal",
            rules_path,
        ),
        buying_intent_re=_compile_pattern(
            _required_str(intent_patterns, "buying_intent", rules_path),
            "intent_patterns.buying_intent",
            rules_path,
        ),
        handoff_phrases=_required_str_tuple(data, "handoff_phrases", rules_path),
        prompt=PromptRules(
            base_system_rules=_required_str_tuple(prompt, "base_system_rules", rules_path),
            seller_already_greeted_rule=_required_str(prompt, "seller_already_greeted_rule", rules_path),
        ),
        post_processing=PostProcessingRules(
            greeting_re=_compile_pattern(
                _required_str(post_processing, "greeting_pattern", rules_path),
                "post_processing.greeting_pattern",
                rules_path,
            ),
            seller_name_address_re=_compile_pattern(
                _required_str(post_processing, "seller_name_address_pattern", rules_path),
                "post_processing.seller_name_address_pattern",
                rules_path,
            ),
            client_name_passthrough=frozenset(
                item.casefold() for item in _required_str_tuple(post_processing, "client_name_passthrough", rules_path)
            ),
            first_marker=_optional_str(reply_formatting, "first_marker", "✅", rules_path),
            middle_marker=_optional_str(reply_formatting, "middle_marker", "💡", rules_path),
            last_marker=_optional_str(reply_formatting, "last_marker", "👉", rules_path),
            single_marker=_optional_str(reply_formatting, "single_marker", "💬", rules_path),
            bullet_marker=_optional_str(reply_formatting, "bullet_marker", "•", rules_path),
            min_inline_list_items=_optional_int(reply_formatting, "min_inline_list_items", 3, rules_path),
        ),
        dialogue_guidance=DialogueGuidanceRules(
            manager_mention_terms=_required_str_tuple(dialogue_guidance, "manager_mention_terms", rules_path),
            manager_mention_threshold=_required_int(dialogue_guidance, "manager_mention_threshold", rules_path),
            detail_signal_threshold=_required_int(dialogue_guidance, "detail_signal_threshold", rules_path),
            handoff_client_reply=_optional_str(
                dialogue_guidance,
                "handoff_client_reply",
                DEFAULT_HANDOFF_CLIENT_REPLY,
                rules_path,
            ),
            base_rules=_required_str_tuple(dialogue_guidance, "base_rules", rules_path),
            known_price_rule=_required_str(dialogue_guidance, "known_price_rule", rules_path),
            price_question_rule=_required_str(dialogue_guidance, "price_question_rule", rules_path),
            timing_question_rule=_required_str(dialogue_guidance, "timing_question_rule", rules_path),
            repeated_manager_rule=_required_str(dialogue_guidance, "repeated_manager_rule", rules_path),
            enough_details_rule=_required_str(dialogue_guidance, "enough_details_rule", rules_path),
        ),
    )


def build_system_prompt(*, seller_already_greeted: bool, admin_mode: bool = False) -> str:
    if admin_mode:
        rules = list(ADMIN_MODE_RULES)
    else:
        rules = list(BASE_SYSTEM_RULES)
    if seller_already_greeted and not admin_mode:
        rules.append(RULES.prompt.seller_already_greeted_rule)
    return " ".join(rules)


def build_dialogue_guidance(
    *,
    client_texts: list[str],
    seller_texts: list[str],
    item_price: str | None = None,
    admin_mode: bool = False,
) -> str:
    if admin_mode:
        return RULES.admin_dialogue_guidance

    latest_client = client_texts[-1] if client_texts else ""
    guidance_rules = RULES.dialogue_guidance
    seller_manager_mentions = sum(
        1
        for text in seller_texts
        if any(term in text.lower() for term in guidance_rules.manager_mention_terms)
    )
    detail_count = sum(1 for text in client_texts if DETAIL_SIGNAL_RE.search(text))

    guidance = list(guidance_rules.base_rules)

    if item_price and item_price != "unknown price":
        guidance.append(guidance_rules.known_price_rule.format(item_price=item_price))

    if PRICE_QUESTION_RE.search(latest_client):
        guidance.append(guidance_rules.price_question_rule)

    if TIMING_QUESTION_RE.search(latest_client):
        guidance.append(guidance_rules.timing_question_rule)

    if seller_manager_mentions >= guidance_rules.manager_mention_threshold:
        guidance.append(guidance_rules.repeated_manager_rule)

    if detail_count >= guidance_rules.detail_signal_threshold:
        guidance.append(guidance_rules.enough_details_rule)

    return " ".join(guidance)


def starts_with_greeting(text: str) -> bool:
    return bool(GREETING_RE.match(text.strip()))


def strip_repeated_greeting(text: str, *, seller_already_greeted: bool) -> str:
    if not seller_already_greeted:
        return text.strip()
    return GREETING_RE.sub("", text, count=1).strip() or text.strip()


def strip_seller_name_address(text: str, *, client_name: str | None = None) -> str:
    if client_name and client_name.casefold() in RULES.post_processing.client_name_passthrough:
        return text.strip()
    return SELLER_NAME_ADDRESS_RE.sub("", text, count=1).strip() or text.strip()


def sanitize_outgoing_text(text: str) -> str:
    cleaned = text.translate(OUTGOING_TEXT_TRANSLATION).replace("```", "")
    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = MARKDOWN_EMPHASIS_RE.sub(lambda match: match.group(1) or match.group(2) or "", cleaned)
    cleaned = INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = MARKDOWN_HEADING_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    return cleaned.strip()


def format_customer_reply(text: str) -> str:
    """Enforce readable plain-text structure when the model ignores style rules."""
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    blocks = [block.strip() for block in re.split(r"\n\s*\n", cleaned) if block.strip()]
    if len(blocks) == 1 and "\n" not in blocks[0]:
        sentences = [sentence.strip() for sentence in SENTENCE_BOUNDARY_RE.split(blocks[0]) if sentence.strip()]
        if 2 <= len(sentences) <= 5:
            blocks = sentences

    formatting = RULES.post_processing
    blocks = [_format_inline_list(block, formatting.bullet_marker, formatting.min_inline_list_items) for block in blocks]
    if len(blocks) == 1:
        markers: dict[int, str] = {0: formatting.single_marker}
    else:
        markers = {0: formatting.first_marker, len(blocks) - 1: formatting.last_marker}
        if len(blocks) > 2:
            markers[1] = formatting.middle_marker

    formatted = []
    for index, block in enumerate(blocks):
        marker = markers.get(index)
        stripped = block.lstrip()
        if marker is None or EMOJI_PREFIX_RE.match(stripped) or stripped.startswith(formatting.bullet_marker):
            formatted.append(block)
        else:
            formatted.append(f"{marker} {block}")
    return "\n\n".join(formatted)


def _format_inline_list(text: str, bullet_marker: str, min_items: int) -> str:
    if "\n" in text or ":" not in text:
        return text
    heading, raw_items = text.split(":", 1)
    candidate = raw_items.strip().rstrip(".")
    if "?" in candidate:
        return text
    items = [item.strip() for item in INLINE_LIST_SEPARATOR_RE.split(candidate) if item.strip()]
    if len(items) < min_items or len(items) > 8:
        return text
    if any(len(item) > 40 or any(mark in item for mark in ".;:!?") for item in items):
        return text
    return f"{heading.strip()}:\n" + "\n".join(f"{bullet_marker} {item}" for item in items)


def enforce_seller_feminine_voice(text: str) -> str:
    cleaned = text
    for pattern, replacement in FEMININE_SELF_REFERENCE_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def redact_admin_code(text: str) -> str:
    if not ADMIN_CODE:
        return text
    return text.replace(ADMIN_CODE, "[admin code hidden]")


def has_buying_intent(text: str) -> bool:
    return bool(text and BUYING_INTENT_RE.search(text))


def _configured_rules_path() -> Path:
    configured_path = os.getenv(RULES_PATH_ENV)
    return Path(configured_path) if configured_path else DEFAULT_RULES_PATH


def _read_rules_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"Could not read bot rules config at {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid bot rules JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Bot rules config at {path} must contain a JSON object")
    return data


def _required_dict(data: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"Bot rules config at {path} must define object '{key}'")
    return value


def _required_str(data: dict[str, Any], key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Bot rules config at {path} must define non-empty string '{key}'")
    return value


def _required_int(data: dict[str, Any], key: str, path: Path) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise RuntimeError(f"Bot rules config at {path} must define integer '{key}'")
    return value


def _optional_str(data: dict[str, Any], key: str, default: str, path: Path) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Bot rules config at {path} must define non-empty string '{key}' when provided")
    return value


def _optional_int(data: dict[str, Any], key: str, default: int, path: Path) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or value < 1:
        raise RuntimeError(f"Bot rules config at {path} must define positive integer '{key}' when provided")
    return value


def _required_str_tuple(data: dict[str, Any], key: str, path: Path) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"Bot rules config at {path} must define non-empty string list '{key}'")
    return tuple(value)


def _compile_pattern(pattern: str, key: str, path: Path) -> re.Pattern[str]:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise RuntimeError(f"Bot rules config at {path} has invalid regex '{key}': {exc}") from exc


def _env_override(env_name: Any, default: str) -> str:
    if isinstance(env_name, str) and env_name:
        return os.getenv(env_name) or default
    return default


RULES = load_bot_rules()
ADMIN_CODE = RULES.admin_code
ADMIN_COMMAND_REASON = RULES.admin_command_reason
ADMIN_MODE_RULES = RULES.admin_mode_rules
ADMIN_DIALOGUE_GUIDANCE = RULES.admin_dialogue_guidance
ADMIN_MODE_DISABLE_RE = RULES.admin_mode_disable_re
PRICE_QUESTION_RE = RULES.price_question_re
TIMING_QUESTION_RE = RULES.timing_question_re
DETAIL_SIGNAL_RE = RULES.detail_signal_re
BUYING_INTENT_RE = RULES.buying_intent_re
HANDOFF_PHRASES = RULES.handoff_phrases
HANDOFF_CLIENT_REPLY = RULES.dialogue_guidance.handoff_client_reply
BASE_SYSTEM_RULES = RULES.prompt.base_system_rules
GREETING_RE = RULES.post_processing.greeting_re
SELLER_NAME_ADDRESS_RE = RULES.post_processing.seller_name_address_re
