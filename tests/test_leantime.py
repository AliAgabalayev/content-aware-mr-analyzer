import json
import pytest
import httpx
import respx
from handlers.leantime import update_task_done

LEANTIME_URL = "http://leantime.test"
API_KEY = "test-key"
JSONRPC_URL = f"{LEANTIME_URL}/api/jsonrpc"


@pytest.mark.asyncio
async def test_update_task_done_success():
    with respx.mock:
        mock = respx.post(JSONRPC_URL).mock(
            return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": True})
        )
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")

    assert result is True
    body = json.loads(mock.calls[0].request.content)
    assert body["method"] == "leantime.rpc.tickets.updateTicket"
    assert body["params"]["id"] == 42
    assert body["params"]["status"] == "done"
    assert mock.calls[0].request.headers["x-api-key"] == API_KEY


@pytest.mark.asyncio
async def test_update_task_done_non_200_http():
    with respx.mock:
        respx.post(JSONRPC_URL).mock(return_value=httpx.Response(401))
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")
    assert result is False


@pytest.mark.asyncio
async def test_update_task_done_non_json_response():
    with respx.mock:
        respx.post(JSONRPC_URL).mock(
            return_value=httpx.Response(200, content=b"not json")
        )
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")
    assert result is False


@pytest.mark.asyncio
async def test_update_task_done_jsonrpc_error():
    with respx.mock:
        respx.post(JSONRPC_URL).mock(
            return_value=httpx.Response(200, json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32600, "message": "Task not found"},
            })
        )
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")
    assert result is False


@pytest.mark.asyncio
async def test_update_task_done_network_error():
    with respx.mock:
        respx.post(JSONRPC_URL).mock(side_effect=httpx.ConnectError("refused"))
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")
    assert result is False


@pytest.mark.asyncio
async def test_update_task_done_result_null_is_success():
    # JSON-RPC 2.0: absence of "error" key = success, regardless of result value
    with respx.mock:
        respx.post(JSONRPC_URL).mock(
            return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": None})
        )
        result = await update_task_done(LEANTIME_URL, API_KEY, 42, "done")
    assert result is True
