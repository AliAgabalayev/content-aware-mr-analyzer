import json
import pytest
import httpx
import respx
from handlers.discord import build_message, send_notification

WEBHOOK_URL = "http://discord.test/webhook"


# build_message

def test_build_message_with_commits():
    msg = build_message(42, "Fix login redirect", ["Fix OAuth", "Update session"])
    assert msg == (
        "✅ Task LT-42 completed\n"
        "MR: Fix login redirect\n"
        "Changes: Fix OAuth · Update session"
    )

def test_build_message_no_commits():
    msg = build_message(42, "Fix login redirect", [])
    assert msg == (
        "✅ Task LT-42 completed\n"
        "MR: Fix login redirect"
    )

def test_build_message_exactly_five_commits():
    subjects = ["A", "B", "C", "D", "E"]
    msg = build_message(1, "Title", subjects)
    assert "Changes: A · B · C · D · E" in msg
    assert "(+" not in msg

def test_build_message_six_commits_shows_overflow():
    subjects = ["A", "B", "C", "D", "E", "F"]
    msg = build_message(1, "Title", subjects)
    assert "Changes: A · B · C · D · E · (+1 more)" in msg

def test_build_message_ten_commits_shows_five_plus_overflow():
    subjects = [str(i) for i in range(10)]
    msg = build_message(1, "Title", subjects)
    assert "(+5 more)" in msg
    # only first 5 commits (0-4) shown
    assert "· 5 ·" not in msg


# send_notification

@pytest.mark.asyncio
async def test_send_notification_posts_correct_message():
    with respx.mock:
        mock = respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(204))
        await send_notification(WEBHOOK_URL, 42, "Fix login redirect", ["Fix OAuth"])
    assert mock.called
    body = json.loads(mock.calls[0].request.content)
    assert "✅ Task LT-42 completed" in body["content"]
    assert "Fix OAuth" in body["content"]

@pytest.mark.asyncio
async def test_send_notification_discord_non_2xx_does_not_raise():
    with respx.mock:
        respx.post(WEBHOOK_URL).mock(return_value=httpx.Response(500))
        await send_notification(WEBHOOK_URL, 42, "Title", [])  # must not raise

@pytest.mark.asyncio
async def test_send_notification_network_error_does_not_raise():
    with respx.mock:
        respx.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectError("refused"))
        await send_notification(WEBHOOK_URL, 42, "Title", [])  # must not raise
