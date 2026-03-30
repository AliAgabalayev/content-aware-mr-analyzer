# Context-Aware MR Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI webhook service that receives GitLab MR merge events, marks the related Leantime task as Done via JSON-RPC, and sends a Discord notification — only on full success.

**Architecture:** Single Python FastAPI service with five focused modules: `config.py` (env vars), `models.py` (Pydantic payload), `handlers/gitlab.py` (validate/filter/extract — pure functions), `handlers/leantime.py` (JSON-RPC call), `handlers/discord.py` (build message + send). `main.py` wires them together at `POST /webhook`. The `src/` directory is the Python root for both runtime (via Docker `COPY src/ .`) and tests (via `pythonpath = ["src"]` in pyproject.toml).

**Tech Stack:** Python 3.12, FastAPI, httpx async (10s timeout), Pydantic v2, python-dotenv, pytest + pytest-asyncio + respx, Docker (python:3.12-alpine).

---

## File Map

| File | Responsibility |
|---|---|
| `src/main.py` | FastAPI app; `POST /webhook` handler; wires all modules |
| `src/config.py` | `Settings` frozen dataclass + `get_settings()` with lru_cache |
| `src/models.py` | `GitLabMRPayload`, `MRAttributes`, `Commit` Pydantic models |
| `src/handlers/__init__.py` | Empty package marker |
| `src/handlers/gitlab.py` | Pure functions: validate token, filter event, extract fields |
| `src/handlers/leantime.py` | `update_task_done()` async — returns bool |
| `src/handlers/discord.py` | `build_message()` pure + `send_notification()` async |
| `tests/__init__.py` | Empty package marker |
| `tests/conftest.py` | Shared fixtures: TEST_SETTINGS, MERGE_HEADERS, MERGE_PAYLOAD |
| `tests/test_config.py` | Settings loading, defaults, missing vars |
| `tests/test_models.py` | Pydantic model parsing |
| `tests/test_gitlab.py` | Unit tests for all gitlab.py pure functions |
| `tests/test_leantime.py` | Unit tests for leantime.py (respx mocked) |
| `tests/test_discord.py` | Unit tests for discord.py (respx mocked) |
| `tests/test_webhook.py` | Integration tests for POST /webhook (full pipeline) |
| `requirements.txt` | Runtime dependencies |
| `requirements-dev.txt` | Test dependencies |
| `pyproject.toml` | pytest config (pythonpath, asyncio_mode) |
| `Dockerfile` | python:3.12-alpine image |
| `.env.example` | Example environment file |

---

### Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pyproject.toml`
- Create: `src/__init__.py` (empty)
- Create: `src/handlers/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `.env.example`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/handlers tests
```

- [ ] **Step 2: Create `requirements.txt`**

```
fastapi
uvicorn[standard]
httpx
pydantic
python-dotenv
```

- [ ] **Step 3: Create `requirements-dev.txt`**

```
pytest
pytest-asyncio
respx
httpx
```

- [ ] **Step 4: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 5: Create empty package markers**

`src/__init__.py` — empty file
`src/handlers/__init__.py` — empty file
`tests/__init__.py` — empty file

- [ ] **Step 6: Create `.env.example`**

```
GITLAB_WEBHOOK_SECRET=your-secret-token
LEANTIME_URL=http://leantime.internal
LEANTIME_API_KEY=your-api-key
LEANTIME_DONE_STATUS=done
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-id/your-token
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Expected: all packages install without error

- [ ] **Step 8: Commit**

```bash
git init
git add .
git commit -m "chore: project scaffold"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
import pytest
from config import get_settings, Settings


def test_get_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "secret123")
    monkeypatch.setenv("LEANTIME_URL", "http://leantime.internal")
    monkeypatch.setenv("LEANTIME_API_KEY", "key123")
    monkeypatch.setenv("LEANTIME_DONE_STATUS", "done")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "http://discord.test/webhook")
    get_settings.cache_clear()

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
    get_settings.cache_clear()

    s = get_settings()

    assert s.leantime_done_status == "done"


def test_get_settings_missing_required_var(monkeypatch):
    monkeypatch.delenv("GITLAB_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(KeyError):
        get_settings()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Create `src/config.py`**

```python
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gitlab_webhook_secret: str
    leantime_url: str
    leantime_api_key: str
    leantime_done_status: str
    discord_webhook_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        gitlab_webhook_secret=os.environ["GITLAB_WEBHOOK_SECRET"],
        leantime_url=os.environ["LEANTIME_URL"],
        leantime_api_key=os.environ["LEANTIME_API_KEY"],
        leantime_done_status=os.environ.get("LEANTIME_DONE_STATUS", "done"),
        discord_webhook_url=os.environ["DISCORD_WEBHOOK_URL"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected:
```
PASSED tests/test_config.py::test_get_settings_reads_env_vars
PASSED tests/test_config.py::test_get_settings_default_done_status
PASSED tests/test_config.py::test_get_settings_missing_required_var
```

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module"
```

---

### Task 3: Pydantic Models

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError
from models import GitLabMRPayload


FULL_PAYLOAD = {
    "object_attributes": {
        "action": "merge",
        "state": "merged",
        "title": "[LT-42] Fix login redirect",
        "url": "http://gitlab.test/mr/1",
    },
    "commits": [
        {"message": "Fix OAuth callback\n\nDetails"},
        {"message": "Update session handling"},
    ],
}


def test_parses_full_payload():
    payload = GitLabMRPayload.model_validate(FULL_PAYLOAD)
    assert payload.object_attributes.action == "merge"
    assert payload.object_attributes.state == "merged"
    assert payload.object_attributes.title == "[LT-42] Fix login redirect"
    assert payload.object_attributes.url == "http://gitlab.test/mr/1"
    assert len(payload.commits) == 2
    assert payload.commits[0].message == "Fix OAuth callback\n\nDetails"


def test_commits_default_to_empty_list():
    payload = GitLabMRPayload.model_validate({
        "object_attributes": {
            "action": "open",
            "state": "opened",
            "title": "No commits here",
            "url": "http://gitlab.test/mr/2",
        }
    })
    assert payload.commits == []


def test_extra_fields_are_ignored():
    data = {
        "object_attributes": {
            **FULL_PAYLOAD["object_attributes"],
            "extra_field": "ignored",
        },
        "commits": FULL_PAYLOAD["commits"],
        "unknown_top_level": "ignored",
    }
    payload = GitLabMRPayload.model_validate(data)
    assert payload.object_attributes.action == "merge"


def test_missing_object_attributes_raises():
    with pytest.raises(ValidationError):
        GitLabMRPayload.model_validate({"commits": []})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create `src/models.py`**

```python
from pydantic import BaseModel


class MRAttributes(BaseModel):
    model_config = {"extra": "ignore"}

    action: str
    state: str
    title: str
    url: str


class Commit(BaseModel):
    model_config = {"extra": "ignore"}

    message: str


class GitLabMRPayload(BaseModel):
    model_config = {"extra": "ignore"}

    object_attributes: MRAttributes
    commits: list[Commit] = []
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected:
```
PASSED tests/test_models.py::test_parses_full_payload
PASSED tests/test_models.py::test_commits_default_to_empty_list
PASSED tests/test_models.py::test_extra_fields_are_ignored
PASSED tests/test_models.py::test_missing_object_attributes_raises
```

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add Pydantic models"
```

---

### Task 4: GitLab Handler

**Files:**
- Create: `src/handlers/gitlab.py`
- Create: `tests/test_gitlab.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_gitlab.py`:
```python
from models import Commit, GitLabMRPayload, MRAttributes
from handlers.gitlab import (
    extract_commit_subjects,
    extract_task_id,
    is_merge_action,
    is_merge_request_hook,
    strip_title_prefix,
    validate_token,
)


# validate_token

def test_validate_token_matches():
    assert validate_token("abc123", "abc123") is True

def test_validate_token_mismatch():
    assert validate_token("wrong", "abc123") is False

def test_validate_token_none():
    assert validate_token(None, "abc123") is False


# is_merge_request_hook

def test_is_merge_request_hook_correct():
    assert is_merge_request_hook("Merge Request Hook") is True

def test_is_merge_request_hook_wrong():
    assert is_merge_request_hook("Push Hook") is False

def test_is_merge_request_hook_none():
    assert is_merge_request_hook(None) is False


# is_merge_action

def _make_payload(action: str, state: str) -> GitLabMRPayload:
    return GitLabMRPayload(
        object_attributes=MRAttributes(
            action=action, state=state, title="[LT-1] Test", url="http://x"
        )
    )

def test_is_merge_action_true():
    assert is_merge_action(_make_payload("merge", "merged")) is True

def test_is_merge_action_wrong_action():
    assert is_merge_action(_make_payload("open", "merged")) is False

def test_is_merge_action_wrong_state():
    assert is_merge_action(_make_payload("merge", "opened")) is False


# extract_task_id

def test_extract_task_id_standard():
    assert extract_task_id("[LT-42] Fix login") == 42

def test_extract_task_id_large_number():
    assert extract_task_id("[LT-1234] Something") == 1234

def test_extract_task_id_no_match():
    assert extract_task_id("Fix login redirect") is None

def test_extract_task_id_wrong_format():
    assert extract_task_id("[LT-abc] Bad ID") is None


# strip_title_prefix

def test_strip_title_prefix_with_space():
    assert strip_title_prefix("[LT-42] Fix login") == "Fix login"

def test_strip_title_prefix_no_space():
    assert strip_title_prefix("[LT-42]Fix login") == "Fix login"

def test_strip_title_prefix_large_id():
    assert strip_title_prefix("[LT-1234] Something") == "Something"


# extract_commit_subjects

def test_extract_commit_subjects_single_line():
    assert extract_commit_subjects([Commit(message="Fix bug")]) == ["Fix bug"]

def test_extract_commit_subjects_multiline():
    assert extract_commit_subjects(
        [Commit(message="Fix bug\n\nDetailed explanation")]
    ) == ["Fix bug"]

def test_extract_commit_subjects_multiple():
    commits = [Commit(message="First fix\nDetails"), Commit(message="Second fix")]
    assert extract_commit_subjects(commits) == ["First fix", "Second fix"]

def test_extract_commit_subjects_empty():
    assert extract_commit_subjects([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_gitlab.py -v
```

Expected: `ModuleNotFoundError: No module named 'handlers'`

- [ ] **Step 3: Create `src/handlers/gitlab.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gitlab.py -v
```

Expected: all 18 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/handlers/gitlab.py tests/test_gitlab.py
git commit -m "feat: add gitlab handler"
```

---

### Task 5: Discord Handler

**Files:**
- Create: `src/handlers/discord.py`
- Create: `tests/test_discord.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_discord.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_discord.py -v
```

Expected: `ModuleNotFoundError: No module named 'handlers.discord'`

- [ ] **Step 3: Create `src/handlers/discord.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_discord.py -v
```

Expected: all 8 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/handlers/discord.py tests/test_discord.py
git commit -m "feat: add discord handler"
```

---

### Task 6: Leantime Handler

**Files:**
- Create: `src/handlers/leantime.py`
- Create: `tests/test_leantime.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_leantime.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_leantime.py -v
```

Expected: `ModuleNotFoundError: No module named 'handlers.leantime'`

- [ ] **Step 3: Create `src/handlers/leantime.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_leantime.py -v
```

Expected: all 6 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/handlers/leantime.py tests/test_leantime.py
git commit -m "feat: add leantime handler"
```

---

### Task 7: FastAPI App + Integration Tests

**Files:**
- Create: `src/main.py`
- Create: `tests/conftest.py`
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 2: Write the failing integration tests**

`tests/test_webhook.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_webhook.py -v
```

Expected: `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 4: Create `src/main.py`**

```python
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
```

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all tests across all test files PASSED

- [ ] **Step 6: Commit**

```bash
git add src/main.py tests/conftest.py tests/test_webhook.py
git commit -m "feat: add FastAPI webhook endpoint with integration tests"
```

---

### Task 8: Dockerfile and Deployment Files

**Files:**
- Create: `Dockerfile`
- Update: `.env.example` already created in Task 1

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: `COPY src/ .` copies the contents of `src/` into `/app/`, so `main.py` is at `/app/main.py` and `uvicorn main:app` resolves correctly.

- [ ] **Step 2: Verify Docker build**

```bash
docker build -t mr-analyzer .
```

Expected: image builds without error, final size ~100MB

- [ ] **Step 3: Verify Leantime params before going live**

The `updateTicket` parameter shape must be confirmed against your Leantime instance before deploying. Run these curl commands against your real Leantime host:

```bash
# Step A: Fetch a known ticket to inspect the status field value
curl -X POST http://YOUR_LEANTIME_HOST/api/jsonrpc \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"jsonrpc":"2.0","method":"leantime.rpc.tickets.getTicket","id":1,"params":{"id":YOUR_TICKET_ID}}'

# Note the "status" field value in the response.
# If your Done status is not the string "done", update LEANTIME_DONE_STATUS in .env.

# Step B: Test updateTicket on a non-critical ticket
curl -X POST http://YOUR_LEANTIME_HOST/api/jsonrpc \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"jsonrpc":"2.0","method":"leantime.rpc.tickets.updateTicket","id":1,"params":{"id":YOUR_TICKET_ID,"status":"done"}}'

# If response has an "error" key, Leantime may require nested params.
# In that case, update src/handlers/leantime.py "params" to:
#   {"id": task_id, "ticket": {"status": done_status}}
# Then re-run: pytest tests/test_leantime.py -v  (tests still pass — params are injected)
```

- [ ] **Step 4: Run and configure**

```bash
cp .env.example .env
# Edit .env with real values
docker run -d --env-file .env -p 8000:8000 --name mr-analyzer mr-analyzer
```

- [ ] **Step 5: Configure GitLab webhook**

In your GitLab project:
1. Go to **Settings → Webhooks → Add new webhook**
2. **URL:** `http://your-server-ip:8000/webhook`
3. **Secret token:** the value of `GITLAB_WEBHOOK_SECRET` in your `.env`
4. **Triggers:** check **Merge request events** only — uncheck everything else
5. Click **Add webhook**
6. Click **Test → Merge request events** — should return HTTP 200

- [ ] **Step 6: Commit**

```bash
git add Dockerfile
git commit -m "chore: add Dockerfile"
```

---

## Spec Coverage Checklist

| Spec requirement | Task |
|---|---|
| `POST /webhook` endpoint | 7 |
| `X-Gitlab-Token` plain equality check → 403 on mismatch | 4, 7 |
| `X-Gitlab-Event: Merge Request Hook` filter | 4, 7 |
| `action == merge AND state == merged` filter | 4, 7 |
| `[LT-(\d+)]` regex, cast to int | 4 |
| Strip prefix with `re.sub(r'^\[LT-\d+\]\s*', '', title)` | 4 |
| Pydantic models with `commits` defaulting to `[]` | 3 |
| Leantime JSON-RPC `updateTicket`, `id` as int | 6 |
| `status` from `LEANTIME_DONE_STATUS` env var | 6, 7 |
| Leantime failure cases: non-200, non-JSON, error field | 6, 7 |
| Discord fires only on Leantime success | 7 |
| Discord message format with `MR:` and `Changes:` lines | 5 |
| Max 5 commits, `(+N more)` where N = total − 5 | 5 |
| Omit `Changes:` line when no commits | 5, 7 |
| Discord failure → return 200, no raise | 5, 7 |
| `httpx.AsyncClient` with 10s timeout | 5, 6 |
| Settings via `Depends(get_settings)` for test overrides | 2, 7 |
| `Dockerfile` `python:3.12-alpine`, uvicorn port 8000 | 8 |
| `.env.example` with all five vars | 1 |
| `requirements.txt` with all runtime deps | 1 |
