import logging

from fastapi import Depends, FastAPI, Header, Request, Response

from config import Settings, get_settings
from handlers.discord import send_notification
from handlers.gitlab import (
    extract_commit_subjects,
    extract_task_id,
    is_merge_action,
    is_merge_request_hook,
    strip_title_prefix,
    validate_token,
)
from handlers.leantime import update_task_done
from models import GitLabMRPayload

logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/webhook")
async def webhook(
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    x_gitlab_event: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Response:
    if not validate_token(x_gitlab_token, settings.gitlab_webhook_secret):
        return Response(status_code=403)

    if not is_merge_request_hook(x_gitlab_event):
        return Response(status_code=200)

    body = await request.json()
    payload = GitLabMRPayload.model_validate(body)

    if not is_merge_action(payload):
        return Response(status_code=200)

    task_id = extract_task_id(payload.object_attributes.title)
    if task_id is None:
        logger.warning(
            "MR title has no [LT-xxx] pattern: %s (url: %s)",
            payload.object_attributes.title,
            payload.object_attributes.url,
        )
        return Response(status_code=200)

    success = await update_task_done(
        settings.leantime_url,
        settings.leantime_api_key,
        task_id,
        settings.leantime_done_status,
    )

    if success:
        mr_title = strip_title_prefix(payload.object_attributes.title)
        commit_subjects = extract_commit_subjects(payload.commits)
        await send_notification(
            settings.discord_webhook_url,
            task_id,
            mr_title,
            commit_subjects,
        )

    return Response(status_code=200)
