from app.core.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 7
    assert s.ai_low_confidence_threshold == 0.70
    assert s.max_upload_size_mb == 10
    assert "ai_support" in s.database_url
