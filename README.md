# Context-Aware MR Analyzer

Automates the handoff between GitLab, Leantime, and Discord when a Merge Request is merged.

**Flow:**
1. Developer merges an MR with a title like `[LT-42] Fix login redirect`
2. GitLab fires a webhook to this service
3. Service marks task `LT-42` as **Done** in Leantime
4. Service posts a summary to your Discord channel

```
[LT-42] Fix login redirect  →  ✅ Task LT-42 completed
                                MR: Fix login redirect
                                Changes: Fix OAuth callback · Update session handling
```

---

## Requirements

- Python 3.12+
- Docker (recommended for deployment)
- Access to your Leantime instance (VPN if self-hosted)
- A Discord webhook URL
- A GitLab project you can configure webhooks on

---

## MR Title Convention

Developers must include the Leantime task ID in the MR title:

```
[LT-{task_id}] Short description

Examples:
  [LT-42] Fix user login redirect after OAuth
  [LT-123] Add export to CSV feature
```

MRs without this pattern are silently ignored.

---

## Setup

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd context-aware-mr-analyzer
cp .env.example .env
```

Edit `.env` with your real values:

```env
GITLAB_WEBHOOK_SECRET=choose-a-strong-random-secret
LEANTIME_URL=http://your-leantime-host
LEANTIME_API_KEY=your-leantime-api-key
LEANTIME_DONE_STATUS=done
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your-id/your-token
```

> **LEANTIME_DONE_STATUS:** Verify the correct value for your instance before deploying.
> Fetch a known Done ticket via the Leantime JSON-RPC API and check its `status` field:
> ```bash
> curl -X POST http://YOUR_LEANTIME/api/jsonrpc \
>   -H "Content-Type: application/json" \
>   -H "x-api-key: YOUR_KEY" \
>   -d '{"jsonrpc":"2.0","method":"leantime.rpc.tickets.getTicket","id":1,"params":{"id":YOUR_TICKET_ID}}'
> ```

### 2. Run with Docker

```bash
docker build -t mr-analyzer .
docker run -d --env-file .env -p 8000:8000 --name mr-analyzer mr-analyzer
```

### 3. Configure GitLab webhook

In your GitLab project: **Settings → Webhooks → Add new webhook**

| Field | Value |
|---|---|
| URL | `http://your-server-ip:8000/webhook` |
| Secret token | Value of `GITLAB_WEBHOOK_SECRET` in your `.env` |
| Triggers | **Merge request events** only |

Click **Test → Merge request events** — should return HTTP 200.

---

## Discord Setup

In Discord: **Server Settings → Integrations → Webhooks → New Webhook**

Copy the webhook URL and paste it as `DISCORD_WEBHOOK_URL` in your `.env`.

---

## Leantime API Key

In Leantime: **Company Settings → API Keys → Create new key**

Assign it access to the projects your team uses.

---

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Run locally (requires .env)
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Wait — when running locally (not Docker), set `PYTHONPATH` so imports resolve:

```bash
PYTHONPATH=src uvicorn main:app --host 0.0.0.0 --port 8000
```

Or use the Docker image for local testing too:

```bash
docker run --env-file .env -p 8000:8000 mr-analyzer
```

---

## Error Handling

The service logs all errors but always returns `200` to GitLab (except for bad webhook secrets) to prevent GitLab from retrying and creating duplicate updates.

| Scenario | Behavior |
|---|---|
| Wrong or missing webhook secret | 403 — GitLab stops retrying |
| Non-MR event type | 200 — ignored silently |
| MR title has no `[LT-xxx]` | 200 — logged as warning |
| Leantime update fails | 200 — logged, Discord skipped |
| Discord notification fails | 200 — logged, does not affect Leantime update |

---

## Project Structure

```
src/
├── main.py              # FastAPI app, POST /webhook
├── config.py            # Environment variable loading
├── models.py            # Pydantic models for GitLab payload
└── handlers/
    ├── gitlab.py        # Token validation, event filtering, field extraction
    ├── leantime.py      # Leantime JSON-RPC client
    └── discord.py       # Discord webhook client
```

---

## License

MIT
