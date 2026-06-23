from app.config import Settings, mask_value


def test_mask_value_hides_middle() -> None:
    assert mask_value("abcdefghijkl") == "abcd...ijkl"


def test_public_status_does_not_expose_secret() -> None:
    settings = Settings(
        avito_client_id="client-id-123",
        avito_client_secret="secret-value",
        avito_user_id=None,
        avito_webhook_url=None,
        deepseek_api_key="deepseek-secret",
        deepseek_model="deepseek-v4-flash",
    )

    status = settings.public_status()

    assert status["avito_client_secret_configured"] is True
    assert "secret-value" not in str(status)
    assert status["deepseek_api_key_configured"] is True
    assert "deepseek-secret" not in str(status)
