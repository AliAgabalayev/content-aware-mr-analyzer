from config import Settings

TEST_SETTINGS = Settings(
    gitlab_webhook_secret="test-secret",
    leantime_url="http://leantime.test",
    leantime_api_key="test-api-key",
    leantime_done_status="done",
    discord_webhook_url="http://discord.test/webhook",
)

MERGE_HEADERS = {
    "X-Gitlab-Token": "test-secret",
    "X-Gitlab-Event": "Merge Request Hook",
}

MERGE_PAYLOAD = {
    "object_attributes": {
        "action": "merge",
        "state": "merged",
        "title": "[LT-42] Fix login redirect",
        "url": "http://gitlab.test/mr/1",
    },
    "commits": [
        {"message": "Fix OAuth callback URL\n\nDetails"},
        {"message": "Update session handling"},
    ],
}
