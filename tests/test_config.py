import pytest
from config import get_settings, Settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "secret123")
    monkeypatch.setenv("LEANTIME_URL", "http://leantime.internal")
    monkeypatch.setenv("LEANTIME_API_KEY", "key123")
    monkeypatch.setenv("LEANTIME_DONE_STATUS", "done")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "http://discord.test/webhook")

    s = get_settings()

    assert s.gitlab_webhook_secret == "secret123"
    assert s.leantime_url == "http://leantime.internal"
    assert s.leantime_api_key == "key123"
    assert s.leantime_done_status == "done"
    assert s.discord_webhook_url == "http://discord.test/webhook"


def test_get_settings_default_done_status(monkeypatch):
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "s")
    monkeypatch.setenv("LEANTIME_URL", "http://x")
    monkeypatch.setenv("LEANTIME_API_KEY", "k")
    monkeypatch.delenv("LEANTIME_DONE_STATUS", raising=False)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "http://d")

    s = get_settings()

    assert s.leantime_done_status == "done"


def test_get_settings_missing_required_var(monkeypatch):
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("LEANTIME_URL", raising=False)
    monkeypatch.delenv("LEANTIME_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    with pytest.raises(KeyError):
        get_settings()
