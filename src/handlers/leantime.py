import logging

import httpx

logger = logging.getLogger(__name__)


async def update_task_done(
    leantime_url: str,
    api_key: str,
    task_id: int,
    done_status: str,
) -> bool:
    payload = {
        "jsonrpc": "2.0",
        "method": "leantime.rpc.tickets.updateTicket",
        "id": 1,
        "params": {
            "id": task_id,
            "status": done_status,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{leantime_url}/api/jsonrpc",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                },
            )
    except Exception as exc:
        logger.error("Leantime request failed for task %s: %s", task_id, exc)
        return False

    if response.status_code != 200:
        logger.error(
            "Leantime returned HTTP %s for task %s", response.status_code, task_id
        )
        return False

    try:
        data = response.json()
    except Exception:
        logger.error("Leantime response is not valid JSON for task %s", task_id)
        return False

    if "error" in data:
        logger.error(
            "Leantime JSON-RPC error for task %s: %s", task_id, data["error"]
        )
        return False

    return True
