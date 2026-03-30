import json
import pytest
import httpx
import respx
from httpx import AsyncClient, ASGITransport

from main import app
from config import get_settings
from tests.conftest import TEST_SETTINGS, MERGE_HEADERS, MERGE_PAYLOAD

LEANTIME_URL = "http://leantime.test/api/jsonrpc"
DISCORD_URL = "http://discord.test/webhook"

LEANTIME_SUCCESS = {"jsonrpc": "2.0", "id": 1, "result": True}


@pytest.fixture(autouse=True)
def override_settings():
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# 1. Invalid token → 403

@pytest.mark.asyncio
async def test_invalid_token_returns_403(client):
    with respx.mock:
        async with client as c:
            response = await c.post(
                "/webhook",
                json=MERGE_PAYLOAD,
                headers={"X-Gitlab-Token": "wrong", "X-Gitlab-Event": "Merge Request Hook"},
            )
    assert response.status_code == 403


# 2. Wrong event type → 200, Leantime not called

@pytest.mark.asyncio
async def test_wrong_event_type_returns_200_no_leantime(client):
    with respx.mock:
        leantime = respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        async with client as c:
            response = await c.post(
                "/webhook",
                json=MERGE_PAYLOAD,
                headers={"X-Gitlab-Token": "test-secret", "X-Gitlab-Event": "Push Hook"},
            )
    assert response.status_code == 200
    assert not leantime.called


# 3. Non-merge action → 200, Leantime not called

@pytest.mark.asyncio
async def test_non_merge_action_returns_200_no_leantime(client):
    payload = {
        **MERGE_PAYLOAD,
        "object_attributes": {
            **MERGE_PAYLOAD["object_attributes"],
            "action": "open",
            "state": "opened",
        },
    }
    with respx.mock:
        leantime = respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        async with client as c:
            response = await c.post("/webhook", json=payload, headers=MERGE_HEADERS)
    assert response.status_code == 200
    assert not leantime.called


# 4. No [LT-xxx] in title → 200, Leantime not called

@pytest.mark.asyncio
async def test_no_task_id_returns_200_no_leantime(client):
    payload = {
        **MERGE_PAYLOAD,
        "object_attributes": {
            **MERGE_PAYLOAD["object_attributes"],
            "title": "Fix login redirect without ID",
        },
    }
    with respx.mock:
        leantime = respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        async with client as c:
            response = await c.post("/webhook", json=payload, headers=MERGE_HEADERS)
    assert response.status_code == 200
    assert not leantime.called


# 4b. Malformed payload → 422

@pytest.mark.asyncio
async def test_malformed_payload_returns_422(client):
    with respx.mock:
        async with client as c:
            response = await c.post(
                "/webhook",
                json={"no_object_attributes": "missing"},
                headers=MERGE_HEADERS,
            )
    assert response.status_code == 422


# 5. Leantime non-200 → 200, Discord not called

@pytest.mark.asyncio
async def test_leantime_non_200_no_discord(client):
    with respx.mock:
        respx.post(LEANTIME_URL).mock(return_value=httpx.Response(500))
        discord = respx.post(DISCORD_URL).mock(return_value=httpx.Response(204))
        async with client as c:
            response = await c.post("/webhook", json=MERGE_PAYLOAD, headers=MERGE_HEADERS)
    assert response.status_code == 200
    assert not discord.called


# 6. Leantime JSON-RPC error → 200, Discord not called

@pytest.mark.asyncio
async def test_leantime_jsonrpc_error_no_discord(client):
    with respx.mock:
        respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json={
                "jsonrpc": "2.0", "id": 1,
                "error": {"code": -32600, "message": "not found"},
            })
        )
        discord = respx.post(DISCORD_URL).mock(return_value=httpx.Response(204))
        async with client as c:
            response = await c.post("/webhook", json=MERGE_PAYLOAD, headers=MERGE_HEADERS)
    assert response.status_code == 200
    assert not discord.called


# 7. Discord fails → still returns 200

@pytest.mark.asyncio
async def test_discord_failure_still_returns_200(client):
    with respx.mock:
        respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        respx.post(DISCORD_URL).mock(return_value=httpx.Response(500))
        async with client as c:
            response = await c.post("/webhook", json=MERGE_PAYLOAD, headers=MERGE_HEADERS)
    assert response.status_code == 200


# 8. Full success — Leantime called with correct params, Discord called with correct message

@pytest.mark.asyncio
async def test_full_success(client):
    with respx.mock:
        leantime = respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        discord = respx.post(DISCORD_URL).mock(return_value=httpx.Response(204))
        async with client as c:
            response = await c.post("/webhook", json=MERGE_PAYLOAD, headers=MERGE_HEADERS)

    assert response.status_code == 200
    assert leantime.called
    assert discord.called

    leantime_body = json.loads(leantime.calls[0].request.content)
    assert leantime_body["params"]["id"] == 42
    assert leantime_body["params"]["status"] == "done"

    discord_body = json.loads(discord.calls[0].request.content)
    assert "✅ Task LT-42 completed" in discord_body["content"]
    assert "MR: Fix login redirect" in discord_body["content"]
    assert "Fix OAuth callback URL" in discord_body["content"]
    assert "Update session handling" in discord_body["content"]


# 9. Full success with no commits — Discord message has no Changes line

@pytest.mark.asyncio
async def test_full_success_no_commits(client):
    payload = {**MERGE_PAYLOAD, "commits": []}
    with respx.mock:
        respx.post(LEANTIME_URL).mock(
            return_value=httpx.Response(200, json=LEANTIME_SUCCESS)
        )
        discord = respx.post(DISCORD_URL).mock(return_value=httpx.Response(204))
        async with client as c:
            response = await c.post("/webhook", json=payload, headers=MERGE_HEADERS)

    assert response.status_code == 200
    discord_body = json.loads(discord.calls[0].request.content)
    assert "Changes:" not in discord_body["content"]
