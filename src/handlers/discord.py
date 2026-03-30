import logging

import httpx

logger = logging.getLogger(__name__)


def build_message(task_id: int, mr_title: str, commit_subjects: list[str]) -> str:
    lines = [
        f"✅ Task LT-{task_id} completed",
        f"MR: {mr_title}",
    ]
    if commit_subjects:
        shown = commit_subjects[:5]
        joined = " · ".join(shown)
        overflow = len(commit_subjects) - 5
        if overflow > 0:
            joined += f" · (+{overflow} more)"
        lines.append(f"Changes: {joined}")
    return "\n".join(lines)


async def send_notification(
    webhook_url: str,
    task_id: int,
    mr_title: str,
    commit_subjects: list[str],
) -> None:
    message = build_message(task_id, mr_title, commit_subjects)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json={"content": message})
        if response.status_code not in (200, 204):
            logger.error("Discord webhook returned HTTP %s", response.status_code)
    except Exception as exc:
        logger.error("Discord notification failed: %s", exc)
