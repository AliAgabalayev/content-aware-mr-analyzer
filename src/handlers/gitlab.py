import re

from models import Commit, GitLabMRPayload

_TASK_ID_RE = re.compile(r'\[LT-(\d+)\]')
_PREFIX_RE = re.compile(r'^\[LT-\d+\]\s*')


def validate_token(token: str | None, secret: str) -> bool:
    return token == secret


def is_merge_request_hook(event: str | None) -> bool:
    return event == "Merge Request Hook"


def is_merge_action(payload: GitLabMRPayload) -> bool:
    return (
        payload.object_attributes.action == "merge"
        and payload.object_attributes.state == "merged"
    )


def extract_task_id(title: str) -> int | None:
    match = _TASK_ID_RE.search(title)
    if match:
        return int(match.group(1))
    return None


def strip_title_prefix(title: str) -> str:
    return _PREFIX_RE.sub('', title)


def extract_commit_subjects(commits: list[Commit]) -> list[str]:
    return [commit.message.split('\n')[0] for commit in commits]
