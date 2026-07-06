from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReplyStrategy(StrEnum):
    AI = "ai"
    OPERATOR = "operator"
    TEMPLATE = "template"
    RULE_BASED = "rule_based"
    HANDOFF_NOTICE = "handoff_notice"
    NO_REPLY = "no_reply"


@dataclass(frozen=True)
class ReplyStrategyDecision:
    strategy: ReplyStrategy
    reason: str
    auto_send_allowed: bool = False
    manager_notification_allowed: bool = False


def select_pre_draft_strategy(
    *,
    manager_takeover: bool,
    latest_message_is_inbound: bool,
    already_processed: bool,
) -> ReplyStrategyDecision:
    if manager_takeover:
        return ReplyStrategyDecision(
            strategy=ReplyStrategy.OPERATOR,
            reason="manager_takeover",
            manager_notification_allowed=True,
        )
    if not latest_message_is_inbound:
        return ReplyStrategyDecision(strategy=ReplyStrategy.NO_REPLY, reason="no_latest_inbound")
    if already_processed:
        return ReplyStrategyDecision(strategy=ReplyStrategy.NO_REPLY, reason="already_processed")
    return ReplyStrategyDecision(strategy=ReplyStrategy.AI, reason="eligible_for_ai", auto_send_allowed=True)


def select_post_draft_strategy(*, handoff_required: bool) -> ReplyStrategyDecision:
    if handoff_required:
        return ReplyStrategyDecision(
            strategy=ReplyStrategy.HANDOFF_NOTICE,
            reason="handoff_required",
            auto_send_allowed=True,
            manager_notification_allowed=True,
        )
    return ReplyStrategyDecision(strategy=ReplyStrategy.AI, reason="ai_reply", auto_send_allowed=True)
