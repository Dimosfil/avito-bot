from app.reply_strategy import ReplyStrategy, select_post_draft_strategy, select_pre_draft_strategy


def test_pre_draft_strategy_prefers_operator_for_manual_takeover() -> None:
    decision = select_pre_draft_strategy(
        manager_takeover=True,
        latest_message_is_inbound=True,
        already_processed=False,
    )

    assert decision.strategy == ReplyStrategy.OPERATOR
    assert decision.reason == "manager_takeover"
    assert decision.auto_send_allowed is False
    assert decision.manager_notification_allowed is True


def test_pre_draft_strategy_skips_non_inbound_messages() -> None:
    decision = select_pre_draft_strategy(
        manager_takeover=False,
        latest_message_is_inbound=False,
        already_processed=False,
    )

    assert decision.strategy == ReplyStrategy.NO_REPLY
    assert decision.reason == "no_latest_inbound"
    assert decision.auto_send_allowed is False


def test_pre_draft_strategy_allows_ai_for_new_inbound_message() -> None:
    decision = select_pre_draft_strategy(
        manager_takeover=False,
        latest_message_is_inbound=True,
        already_processed=False,
    )

    assert decision.strategy == ReplyStrategy.AI
    assert decision.reason == "eligible_for_ai"
    assert decision.auto_send_allowed is True


def test_post_draft_strategy_selects_handoff_notice() -> None:
    decision = select_post_draft_strategy(handoff_required=True)

    assert decision.strategy == ReplyStrategy.HANDOFF_NOTICE
    assert decision.reason == "handoff_required"
    assert decision.auto_send_allowed is True
    assert decision.manager_notification_allowed is True
