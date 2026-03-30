# Context-Aware MR Analyzer — Design Spec

**Date:** 2026-03-30
**Status:** Approved

---

## Overview

A lightweight webhook service that listens for GitLab Merge Request merge events. When an MR is merged, it parses the task ID from the MR title, marks the corresponding Leantime task as Done, and sends a summary notification to a Discord channel — but only if the Leantime update succeeds.

---

## MR Title Template

Developers must follow this format for the system to process the MR:

```
[LT-{task_id}] Short description of the change

Example: [LT-42] Fix user login redirect after OAuth
```

- Task ID is extracted with regex: `\[LT-(\d+)\]`, capture group cast to `int`
- The `[LT-xx] ` prefix is stripped for the Discord MR line using: `re.sub(r'^\[LT-\d+\]\s*', '', title)`
- The space after `]` is optional (handled by `\s*`)

If the title does not match, return `200`, log a warning, and stop.

---

## Architecture

Single Python (FastAPI) service running inside the company VPN. Stateless — no database. GitLab calls `POST /webhook` on every MR merge event.

```
GitLab MR merged
      │
      │  POST /webhook
      │  X-Gitlab-Token: <secret>
      │  X-Gitlab-Event: Merge Request Hook
      ▼
┌─────────────────────────────────┐
│       FastAPI Webhook Service   │
│                                 │
│  1. Validate X-Gitlab-Token     │
│  2. Filter by X-Gitlab-Event    │
│  3. Filter: action == "merge"   │
│  4. Parse MR title → task ID    │
│  5. Call Leantime JSON-RPC API  │
│     → set task status: Done     │
│  6. Build change summary        │
│  7. POST to Discord webhook     │
│  8. Return 200                  │
└─────────────────────────────────┘
```

The handler **awaits** both the Leantime call and the Discord call before returning `200`. GitLab has a generous webhook timeout (10s+); both calls have explicit timeouts (see below) well within that limit.

---

## Project Structure

```
context-aware-mr-analyzer/
├── src/
│   ├── main.py              # FastAPI app, registers POST /webhook
│   ├── config.py            # Env vars (secrets, URLs, status value)
│   ├── models.py            # Pydantic models for GitLab webhook payload
│   └── handlers/
│       ├── gitlab.py        # Validate, filter, extract
│       ├── leantime.py      # JSON-RPC updateTicket
│       └── discord.py       # Discord webhook message sender
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Dependencies

`requirements.txt`:

```
fastapi
uvicorn[standard]
httpx
pydantic
python-dotenv
```

All outbound HTTP calls use **`httpx` async** (`httpx.AsyncClient`) with a **10-second timeout** on both Leantime and Discord calls.

---

## Data Flow

### 1. Receive & Validate

- `X-Gitlab-Token` header compared via plain `==` to `GITLAB_WEBHOOK_SECRET`. Mismatch → `403`, stop. (GitLab sends a static token, not HMAC — plain equality is correct.)
- `X-Gitlab-Event` header must equal `"Merge Request Hook"`. Anything else → `200`, stop silently.

### 2. Filter Event

Process only when **both** are true in the payload:

- `object_attributes.action == "merge"`
- `object_attributes.state == "merged"`

All other MR actions (opened, updated, closed) → `200`, stop silently.

### 3. Extract Fields

| Field | Source | Notes |
|---|---|---|
| Task ID | `object_attributes.title` → regex `\[LT-(\d+)\]` | Cast to `int` |
| Discord MR line | `object_attributes.title` | Strip prefix: `re.sub(r'^\[LT-\d+\]\s*', '', title)` |
| MR URL | `object_attributes.url` | For logging only (not in Discord message v1) |
| Commit subjects | `commits[].message` | First line of each message (split on `\n`, take index 0) |

### 4. Pydantic Payload Model

```python
class MRAttributes(BaseModel):
    action: str
    state: str
    title: str
    url: str

class Commit(BaseModel):
    message: str

class GitLabMRPayload(BaseModel):
    object_attributes: MRAttributes
    commits: list[Commit] = []   # optional, defaults to empty list
```

All other GitLab payload fields are ignored.

### 5. Update Leantime Task

**Endpoint:** `POST {LEANTIME_URL}/api/jsonrpc`

**Headers:**
```
Content-Type: application/json
x-api-key: {LEANTIME_API_KEY}
```

**Request body (JSON-RPC 2.0):**
```json
{
  "jsonrpc": "2.0",
  "method": "leantime.rpc.tickets.updateTicket",
  "id": 1,
  "params": {
    "id": 42,
    "status": "done"
  }
}
```

- `params.id` is an **integer** (cast from regex capture)
- `params.status` is the raw string value of `LEANTIME_DONE_STATUS` env var, passed verbatim

> **Important — verify params shape before deploying:** The exact parameter structure for `updateTicket` must be confirmed against your Leantime instance. The flat shape `{"id": 42, "status": "done"}` shown above is the expected structure. To verify: call `leantime.rpc.tickets.getTicket` with a known ticket ID, inspect the response shape, then test `updateTicket` with a non-critical ticket before going live. If Leantime requires a nested shape (e.g. `{"id": 42, "ticket": {"status": "done"}}`), update `leantime.py` accordingly.

**Success:** HTTP `200` + valid JSON response body where the `error` key is **absent** (per JSON-RPC 2.0, absence of `error` means success regardless of the `result` value).

**Failure cases (all stop processing, no Discord):**

| Case | Detection |
|---|---|
| Non-200 HTTP status | `response.status_code != 200` |
| Non-JSON response body | JSON parse raises exception |
| JSON-RPC error | `"error"` key present in parsed response |

### 6. Build Discord Message

```
✅ Task LT-42 completed
MR: Fix user login redirect after OAuth
Changes: Fixed OAuth callback URL · Updated session handling · Added redirect tests
```

Rules:
- `MR:` line: MR title with `[LT-xx] ` prefix stripped
- `Changes:` line: join first-line subjects of commits with ` · `
- Maximum **5 commits** shown; if more: append ` · (+N more)` where **N = total_commits − 5**
- If `commits` is empty or absent: omit the `Changes:` line entirely

### 7. Send Discord Notification

**Endpoint:** `POST {DISCORD_WEBHOOK_URL}`

**Headers:** `Content-Type: application/json`

**Body:**
```json
{
  "content": "✅ Task LT-42 completed\nMR: Fix user login redirect after OAuth\nChanges: Fixed OAuth callback URL · Updated session handling"
}
```

---

## Error Handling

| Failure | Behavior |
|---|---|
| `X-Gitlab-Token` missing or wrong | Return `403`, log, stop |
| `X-Gitlab-Event` is not `Merge Request Hook` | Return `200`, stop silently |
| MR `action`/`state` is not merge/merged | Return `200`, stop silently |
| MR title has no `[LT-xxx]` | Return `200`, log warning, stop |
| Leantime HTTP status is not 200 | Log HTTP status, return `200`, stop — no Discord |
| Leantime response is not valid JSON | Log parse error, return `200`, stop — no Discord |
| Leantime JSON-RPC `error` field present | Log error + task ID, return `200`, stop — no Discord |
| Discord webhook fails | Log error, return `200` |

**Key rules:**
- Always return `200` to GitLab (except bad secret) to prevent retries and duplicate updates
- Discord fires **only** after Leantime update fully succeeds
- The handler runs Leantime and Discord calls sequentially (async/await) before returning — but a Discord delivery failure does **not** change the `200` response returned to GitLab
- No retry logic in v1; failures visible via container logs

---

## Configuration

```env
GITLAB_WEBHOOK_SECRET=your-secret-token
LEANTIME_URL=http://leantime.internal
LEANTIME_API_KEY=your-api-key
LEANTIME_DONE_STATUS=done
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

`LEANTIME_DONE_STATUS` — the raw `status` value accepted by `leantime.rpc.tickets.updateTicket`. Verify by fetching a known Done ticket via `leantime.rpc.tickets.getTicket` and reading its `status` field. Common default: `"done"`.

---

## Deployment

### Dockerfile

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Run

```bash
docker build -t mr-analyzer .
docker run -d --env-file .env -p 8000:8000 mr-analyzer
```

### GitLab Webhook Setup

- **URL:** `http://your-internal-server:8000/webhook`
- **Trigger:** Merge request events only
- **Secret token:** must match `GITLAB_WEBHOOK_SECRET` in `.env`
- GitLab sends the secret in the `X-Gitlab-Token` request header

---

## Out of Scope (v1)

- Retry logic for failed external calls
- Per-project Discord channels
- Multiple task management systems
- MR status transitions other than merge (e.g., open → in review)
- Web UI or dashboard
- Mentioning the MR author or MR URL in Discord notifications
