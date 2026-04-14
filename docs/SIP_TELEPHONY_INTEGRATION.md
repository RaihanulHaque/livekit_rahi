# SIP Telephony Integration Guide

Complete technical reference for integrating the SIP telephony backend into your production project.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Services & What to Deploy](#services--what-to-deploy)
3. [SIP API Reference](#sip-api-reference)
4. [Webhook API Reference](#webhook-api-reference)
5. [Data Flow: Registering a Phone Number](#data-flow-registering-a-phone-number)
6. [Data Flow: Incoming Call Lifecycle](#data-flow-incoming-call-lifecycle)
7. [Data Flow: Transcript & Call Record](#data-flow-transcript--call-record)
8. [Redis Schema](#redis-schema)
9. [Integration with Production Backend](#integration-with-production-backend)
10. [Frontend Integration](#frontend-integration)
11. [Environment Variables](#environment-variables)
12. [Scaling & Multi-Worker](#scaling--multi-worker)
13. [File Reference](#file-reference)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Production Backend                      │
│  (manages agents, system prompts, users, DB)                     │
│                                                                  │
│  Calls SIP API to register/manage phone numbers                  │
│  Receives call records + transcripts via webhook or polling      │
└────────┬──────────────────────────────────────────┬──────────────┘
         │ HTTP                                     │ HTTP (webhook callback)
         ▼                                          ▼
┌─────────────────┐                    ┌──────────────────────────┐
│    SIP API       │                    │   Your Webhook Endpoint  │
│  (FastAPI:8089)  │◄── LiveKit ──────►│   (receives call end +   │
│                  │    Webhooks        │    transcript data)      │
│ - POST /sip/agents (register)        │                          │
│ - GET  /sip/agents (list)            └──────────────────────────┘
│ - PATCH/DELETE agents                         ▲
│ - POST /webhook (LiveKit events)              │
└───────┬─────────┘                             │
        │                                       │
        ▼                                       │
┌───────────────┐     ┌──────────────┐   ┌──────┴───────┐
│    Redis       │◄───►│ LiveKit      │   │ LiveKit      │
│ (state store)  │     │ Server:7880  │   │ Agent Worker │
└───────────────┘     └──────┬───────┘   └──────────────┘
                             │                    ▲
                      ┌──────┴───────┐            │
                      │ LiveKit SIP  │            │
                      │  :5060       │────────────┘
                      └──────────────┘
                             ▲
                             │ SIP INVITE
                      ┌──────┴───────┐
                      │  SIP Provider │
                      │  (Telnyx,    │
                      │   Twilio...) │
                      └──────────────┘
                             ▲
                             │ PSTN
                        ☎ Caller
```

### Service Roles

| Service | Image / Code | Role |
|---------|-------------|------|
| **SIP API** | `livekit_agent/Dockerfile.sip` | REST API for agent/phone management + webhook receiver |
| **LiveKit Server** | `livekit/livekit-server` | WebRTC server, room management, webhook dispatch |
| **LiveKit SIP** | `livekit/sip` | SIP-to-WebRTC gateway, handles INVITE/BYE |
| **LiveKit Agent** | `livekit_agent/Dockerfile` | Python agent worker — runs STT/LLM/TTS pipeline, captures transcripts |
| **Redis** | `redis:7-alpine` | Shared state: agent configs, call records, transcripts |

---

## Services & What to Deploy

### What your production project needs to run:

| Service | Required? | Notes |
|---------|-----------|-------|
| **LiveKit Server** | Yes | Core WebRTC server. Use LiveKit Cloud or self-host |
| **LiveKit SIP** | Yes | SIP gateway. Self-host only (not available on LiveKit Cloud free tier) |
| **Redis** | Yes | Already required by LiveKit. SIP API uses the same instance |
| **SIP API** | Yes | The FastAPI server you integrate into your backend |
| **LiveKit Agent** | Yes | The Python voice agent worker(s) |

### What you DON'T need from this repo:

- `frontend/` — your project has its own frontend
- `frontend/app/api/sip/` — the Next.js proxy route (your backend calls SIP API directly)

---

## SIP API Reference

**Base URL:** `http://sip_api:8089` (internal) or `http://localhost:8089` (dev)

All endpoints require `Authorization: Bearer <JWT>` header (LiveKit JWT or your own auth).

### POST /sip/agents — Register Agent with Phone Number

Creates a LiveKit SIP inbound trunk + dispatch rule and stores the mapping in Redis.

**Request:**
```json
{
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "system_prompt": "You are a professional car dealer...",
  "stt": "deepgram",
  "llm": "google",
  "tts": "elevenlabs"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | Yes | Unique agent identifier (from your DB) |
| `local_number` | string | Yes | User-facing phone number |
| `sip_number` | string | Yes | SIP provider number (from Telnyx/Twilio) |
| `system_prompt` | string | Yes | System prompt for the voice agent |
| `stt` | string | Yes | STT provider: `deepgram`, `whisper` |
| `llm` | string | Yes | LLM provider: `langchain`, `openai`, `groq`, `google` |
| `tts` | string | Yes | TTS provider: `elevenlabs`, `openai`, `kokoro` |

**Response (201):**
```json
{
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "trunk_id": "ST_uPnychpk7fPF",
  "dispatch_rule_id": "SDR_QdxFzE5ckwNS",
  "system_prompt": "You are a professional car dealer...",
  "stt": "deepgram",
  "llm": "google",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

**Production integration:** Your backend calls this when a user configures a phone number for their agent. The `agent_id` should match your DB's agent ID. The `system_prompt` and provider configs come from your DB.

### GET /sip/agents — List All Agents

**Response (200):**
```json
[
  {
    "agent_id": "car-dealer-1",
    "local_number": "09643234042",
    "sip_number": "12707768622",
    "status": "active",
    "created_at": 1712973600
  }
]
```

### GET /sip/agents/{agent_id} — Get Agent Config

**Response (200):** Full agent config (same as register response).

### PATCH /sip/agents/{agent_id} — Update Agent Config

Update system prompt or provider settings. Only send fields you want to change.

**Request:**
```json
{
  "system_prompt": "Updated prompt...",
  "tts": "openai"
}
```

**Response (200):** Full updated agent config.

**Production integration:** Call this when a user updates their agent's settings in your app.

### DELETE /sip/agents/{agent_id} — Delete Agent

Removes the dispatch rule, frees the SIP number, deletes from Redis. Does NOT delete the SIP trunk (trunks are tied to provider numbers and can be reused).

**Response (200):**
```json
{
  "deleted": true,
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622"
}
```

---

## Webhook API Reference

**Endpoint:** `POST /webhook`

LiveKit Server sends webhook events here. Configured via `LIVEKIT_CONFIG` env var on the LiveKit server:

```yaml
webhook:
  api_key: devkey
  urls:
    - http://sip_api:8089/webhook
```

### Events Handled

| Event | What Happens |
|-------|-------------|
| `room_started` | Creates call record in Redis with `status: active` |
| `participant_joined` | Appends participant to `participants_joined[]` |
| `participant_left` | Appends participant to `participants_left[]` |
| `room_finished` | Computes duration, sets `status: completed`, reads transcript from Redis |
| `participant_connection_aborted` | Sets `status: aborted` |

### Call Record Written to Redis

After a call completes, the full record at `call:{agent_id}:{room_name}` looks like:

```json
{
  "room_name": "sip-default_-Car dealer-_12707768622_xMUZdbmsAmaP",
  "agent_id": "Car dealer",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "started_at": 1712973600,
  "ended_at": 1712973660,
  "duration_seconds": 60,
  "status": "completed",
  "participants_joined": [
    {"identity": "sip_12707768622", "kind": "3", "joined_at": 1712973601},
    {"identity": "agent-AJ_xyz", "kind": "4", "joined_at": 1712973602}
  ],
  "participants_left": [
    {"identity": "sip_12707768622", "left_at": 1712973658},
    {"identity": "agent-AJ_xyz", "left_at": 1712973659}
  ],
  "transcript": [
    {"role": "user", "content": "Hi, I want to look at cars", "total_tokens": 0},
    {"role": "assistant", "content": "Welcome! What are you looking for?", "total_tokens": 0},
    {"role": "user", "content": "The Helix, is it good?", "total_tokens": 0},
    {"role": "assistant", "content": "Great choice! The Helix is...", "total_tokens": 0},
    {"role": "user", "content": "Thanks, bye", "total_tokens": 0},
    {"role": "assistant", "content": "Don't be a stranger! Come back anytime.", "total_tokens": 0}
  ]
}
```

### Participant Kind Values

| Kind | Meaning |
|------|---------|
| `3` | SIP participant (the phone caller) |
| `4` | Agent participant (the voice AI) |

---

## Data Flow: Registering a Phone Number

```
Your Backend                    SIP API (:8089)              LiveKit Server         Redis
     │                              │                             │                   │
     │  POST /sip/agents            │                             │                   │
     │  {agent_id, sip_number,      │                             │                   │
     │   system_prompt, stt/llm/tts}│                             │                   │
     │─────────────────────────────►│                             │                   │
     │                              │  create_sip_inbound_trunk() │                   │
     │                              │────────────────────────────►│                   │
     │                              │  trunk_id ◄────────────────│                   │
     │                              │                             │                   │
     │                              │  create_sip_dispatch_rule() │                   │
     │                              │  (with room metadata:       │                   │
     │                              │   system_prompt, stt,       │                   │
     │                              │   llm, tts, agent_id)       │                   │
     │                              │────────────────────────────►│                   │
     │                              │  dispatch_rule_id ◄────────│                   │
     │                              │                             │                   │
     │                              │  SET agent:{user}:{agent_id}│                   │
     │                              │─────────────────────────────────────────────────►│
     │                              │                             │                   │
     │  ◄─ {agent_id, trunk_id,     │                             │                   │
     │      dispatch_rule_id, ...}  │                             │                   │
     │                              │                             │                   │
```

**Key point:** The `system_prompt` and provider config are embedded in the dispatch rule's `room_config.metadata`. When a call comes in, LiveKit creates a room with this metadata, and the agent reads it to configure itself.

---

## Data Flow: Incoming Call Lifecycle

```
Phone Caller         SIP Provider       LiveKit SIP       LiveKit Server      Agent Worker        Redis           SIP API
     │                    │                  │                  │                  │                 │                │
     │  Dial number       │                  │                  │                  │                 │                │
     │───────────────────►│                  │                  │                  │                 │                │
     │                    │  SIP INVITE      │                  │                  │                 │                │
     │                    │─────────────────►│                  │                  │                 │                │
     │                    │                  │  Match trunk     │                  │                 │                │
     │                    │                  │  Match dispatch  │                  │                 │                │
     │                    │                  │  rule            │                  │                 │                │
     │                    │                  │                  │                  │                 │                │
     │                    │                  │  Create room     │                  │                 │                │
     │                    │                  │  with metadata   │                  │                 │                │
     │                    │                  │─────────────────►│                  │                 │                │
     │                    │                  │                  │                  │                 │                │
     │                    │                  │                  │  Webhook:        │                 │                │
     │                    │                  │                  │  room_started    │                 │                │
     │                    │                  │                  │─────────────────────────────────────────────────────►│
     │                    │                  │                  │                  │                 │   Store call   │
     │                    │                  │                  │                  │                 │◄───record──────│
     │                    │                  │                  │                  │                 │                │
     │                    │                  │                  │  Dispatch agent  │                 │                │
     │                    │                  │                  │─────────────────►│                 │                │
     │                    │                  │                  │                  │                 │                │
     │                    │                  │                  │                  │  Read metadata  │                │
     │                    │                  │                  │                  │  Extract:       │                │
     │                    │                  │                  │                  │  - system_prompt│                │
     │                    │                  │                  │                  │  - stt/llm/tts  │                │
     │                    │                  │                  │                  │  - agent_id     │                │
     │                    │                  │                  │                  │                 │                │
     │◄═══════════════════════════════════════════════════════════════════════════►│                 │                │
     │              Voice conversation (STT → LLM → TTS)       │                  │                 │                │
     │              Transcript captured per turn                │                  │                 │                │
     │                    │                  │                  │                  │                 │                │
     │  Hang up           │                  │                  │                  │                 │                │
     │───────────────────►│  BYE             │                  │                  │                 │                │
     │                    │─────────────────►│                  │                  │                 │                │
     │                    │                  │                  │                  │                 │                │
     │                    │                  │                  │  Session close   │                 │                │
     │                    │                  │                  │◄────────────────│                 │                │
     │                    │                  │                  │                  │  Save transcript│                │
     │                    │                  │                  │                  │────────────────►│                │
     │                    │                  │                  │                  │                 │                │
     │                    │                  │                  │  Webhook:        │                 │                │
     │                    │                  │                  │  room_finished   │                 │                │
     │                    │                  │                  │─────────────────────────────────────────────────────►│
     │                    │                  │                  │                  │                 │  Read call     │
     │                    │                  │                  │                  │                 │◄──record +     │
     │                    │                  │                  │                  │                 │  transcript    │
     │                    │                  │                  │                  │                 │                │
```

---

## Data Flow: Transcript & Call Record

### How transcripts are captured

1. **During the call** — the agent process listens to two events:
   - `user_input_transcribed` (STT final results) → appends `{"role": "user", "content": "...", "total_tokens": 0}`
   - `conversation_item_added` (LLM responses) → appends `{"role": "assistant", "content": "...", "total_tokens": 0}`

2. **On session close** — agent writes transcript to Redis key `call:{agent_id}:{room_name}`

3. **On `room_finished` webhook** — SIP API reads the Redis record (with transcript) and logs it

### Transcript format

```json
[
  {"role": "user", "content": "Hi, I need help", "total_tokens": 0},
  {"role": "assistant", "content": "Hello! How can I help?", "total_tokens": 0},
  {"role": "user", "content": "What's the price?", "total_tokens": 0},
  {"role": "assistant", "content": "The price is $25,000", "total_tokens": 0}
]
```

- `total_tokens` is `0` for SIP calls (token counting not available at the agent level for SIP). Your backend can compute this if needed.
- For web-based calls, the frontend captures the conversation directly from LLM/TTS output and can include token counts.

### How to get the transcript in your production backend

**Option A: Poll Redis after call ends**

Your backend already knows when a call ends (via your own webhook or by polling). Read from Redis:

```python
import redis, json

r = redis.Redis(host="redis", port=6379, decode_responses=True)

# Key pattern: call:{agent_id}:{room_name}
# List all calls for an agent:
keys = r.keys("call:car-dealer-1:*")
for key in keys:
    record = json.loads(r.get(key))
    print(record["transcript"])
    print(record["duration_seconds"])
    print(record["status"])
```

**Option B: Add a callback webhook to your backend (recommended)**

Modify `_handle_room_finished` in `webhook_api.py` to POST the call record to your backend:

```python
# In _handle_room_finished, after saving to Redis:
import httpx

YOUR_BACKEND_URL = os.environ.get("CALLBACK_WEBHOOK_URL", "")
if YOUR_BACKEND_URL:
    try:
        httpx.post(
            f"{YOUR_BACKEND_URL}/api/call-completed",
            json={
                "agent_id": agent_id,
                "room_name": room_name,
                "local_number": local_number,
                "sip_number": sip_number,
                "duration_seconds": duration_seconds,
                "status": "completed",
                "transcript": transcript,
            },
            timeout=10,
        )
    except Exception as e:
        logger.error("Failed to notify backend: %s", e)
```

**Option C: Add a GET endpoint to SIP API**

Add an endpoint to `sip_api.py` that returns call records:

```
GET /sip/calls?agent_id=car-dealer-1
GET /sip/calls/{room_name}
```

---

## Redis Schema

### Agent Config (written by SIP API)

```
Key:   agent:{user_id}:{agent_id}
TTL:   None (permanent until deleted)
Value: {
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "trunk_id": "ST_xxx",
  "dispatch_rule_id": "SDR_xxx",
  "system_prompt": "...",
  "stt": "deepgram",
  "llm": "google",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

### SIP Number Ownership (written by SIP API)

```
Key:   sip:{user_id}:{sip_number}:owner
TTL:   None
Value: "car-dealer-1"  (agent_id that owns this number)
```

### Call Record (written by Webhook + Agent)

```
Key:   call:{agent_id}:{room_name}
TTL:   30 days
Value: {
  "room_name": "sip-default_-car-dealer-1-_12707768622_abc123",
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "started_at": 1712973600,
  "ended_at": 1712973660,
  "duration_seconds": 60,
  "status": "completed",
  "participants_joined": [...],
  "participants_left": [...],
  "transcript": [
    {"role": "user", "content": "...", "total_tokens": 0},
    {"role": "assistant", "content": "...", "total_tokens": 0}
  ]
}
```

---

## Integration with Production Backend

### What to copy into your backend

| File | Purpose | Modify? |
|------|---------|---------|
| `sip_manager.py` | Core business logic — creates trunks/dispatch rules in LiveKit | No (use as-is) |
| `sip_api.py` | REST endpoints for agent CRUD | Yes — replace JWT validation with your auth |
| `webhook_api.py` | LiveKit webhook receiver | Yes — add callback to your DB |
| `sip_api_server.py` | FastAPI server entrypoint | Yes — or mount routers in your existing FastAPI app |

### Authentication changes

Currently `sip_api.py` uses a placeholder JWT validator (`validate_jwt`). Replace with your production auth:

```python
# Replace this:
async def validate_jwt(request: Request) -> dict:
    user_id = "default_user"
    return {"user_id": user_id, "token": token}

# With your auth:
async def validate_jwt(request: Request) -> dict:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    user = await your_auth_service.verify(token)
    return {"user_id": user.id, "token": token}
```

### System prompt source

Currently the system prompt is passed directly in the `POST /sip/agents` request body. In production:

1. Your backend stores agent configs in its own DB
2. When registering a SIP number, your backend reads the agent's system prompt from DB
3. Passes it to `POST /sip/agents`
4. When the agent config changes, your backend calls `PATCH /sip/agents/{agent_id}` to update

### Saving transcripts to your DB

When a call ends, the transcript is in Redis at `call:{agent_id}:{room_name}`. To persist to your DB:

**Recommended approach:** Add a callback in `_handle_room_finished`:

```python
# After the transcript is read from Redis, POST to your backend:
requests.post("https://your-backend/api/calls/completed", json={
    "agent_id": agent_id,
    "duration_seconds": duration_seconds,
    "transcript": transcript,  # Already in your target format
})
```

Your backend then stores it in your DB alongside the agent record.

### Mounting in existing FastAPI app

If your backend is already FastAPI, skip `sip_api_server.py` and mount the routers directly:

```python
from sip_api import router as sip_router
from webhook_api import router as webhook_router

app = FastAPI(title="Your Backend")
app.include_router(sip_router)      # Adds /sip/agents/* endpoints
app.include_router(webhook_router)   # Adds /webhook endpoint
```

---

## Frontend Integration

### For your frontend team

The SIP management is backend-to-backend — the frontend only needs to:

1. **Show phone number assignment UI** — form with agent selection + SIP number input
2. **Call your backend API** — NOT the SIP API directly
3. **Display call history** — read from your backend DB

### API calls the frontend makes (to YOUR backend, not SIP API)

```
POST   /api/agents/{id}/phone    → Your backend → POST /sip/agents
GET    /api/agents/{id}/phone    → Your backend → GET /sip/agents/{id}
PATCH  /api/agents/{id}/phone    → Your backend → PATCH /sip/agents/{id}
DELETE /api/agents/{id}/phone    → Your backend → DELETE /sip/agents/{id}
GET    /api/agents/{id}/calls    → Your backend → Read from your DB
GET    /api/calls/{id}/transcript → Your backend → Read from your DB
```

### Web voice agent vs SIP voice agent

| Aspect | Web (already done) | SIP (this integration) |
|--------|-------------------|----------------------|
| Connection | Browser WebRTC via LiveKit SDK | Phone → SIP provider → LiveKit SIP |
| Config source | Frontend sends via JWT metadata | Dispatch rule metadata (from SIP API) |
| Transcript | Frontend captures from LLM/TTS output | Agent captures via SDK events → Redis |
| Token counting | Frontend has access | Not available (`total_tokens: 0`) |
| Provider selection | User picks in UI | Set at registration time via API |

---

## Environment Variables

### SIP API Service

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REDIS_HOST` | `redis` | Yes | Redis hostname |
| `REDIS_PORT` | `6379` | Yes | Redis port |
| `LIVEKIT_API_KEY` | `devkey` | Yes | LiveKit API key (for webhook validation) |
| `LIVEKIT_API_SECRET` | `secret` | Yes | LiveKit API secret |
| `LIVEKIT_URL` | `ws://livekit:7880` | Yes | LiveKit server URL (used by SIPManager) |

### LiveKit Server (webhook config)

Set via `LIVEKIT_CONFIG` env var:

```yaml
webhook:
  api_key: <your-livekit-api-key>
  urls:
    - http://sip_api:8089/webhook
```

### LiveKit SIP (`sip.yaml`)

```yaml
api_key: <your-livekit-api-key>
api_secret: <your-livekit-api-secret>
ws_url: ws://<livekit-server-host>:7880
redis:
  address: <redis-host>:6379
sip_port: 5060
rtp_port: 10000-10100
external_ip: <your-server-public-ip>
```

**Important:** If `livekit-sip` uses `network_mode: host`, use `localhost` for `ws_url` and `redis.address` (since LiveKit and Redis expose ports to the host). If on Docker bridge network, use service names.

---

## Scaling & Multi-Worker

### LiveKit Agent Workers

- Each `livekit_agent` container is one **worker**
- Each worker handles multiple rooms, each in a **forked process** (isolated memory)
- Transcript capture runs per-process — no shared state, no race conditions
- All workers write to the **same Redis** — transcripts are accessible regardless of which worker handled the call

### Scaling the agent

```yaml
# docker-compose scale:
docker compose up --scale livekit_agent=3

# Or in production, run multiple containers behind LiveKit's built-in load balancing
```

LiveKit server automatically distributes jobs across registered workers. No extra config needed.

### SIP API

- Stateless (all state in Redis) — can be scaled horizontally
- Webhook endpoint must be reachable from LiveKit server
- If running multiple instances, put behind a load balancer and update the webhook URL

### Redis

- Single instance is fine for most workloads
- For HA, use Redis Sentinel or Redis Cluster
- Call records have 30-day TTL — Redis won't grow unboundedly

---

## File Reference

### Backend Files (to integrate)

| File | Lines | Purpose |
|------|-------|---------|
| `livekit_agent/src/sip_manager.py` | ~450 | Core: creates/deletes LiveKit SIP trunks + dispatch rules, Redis storage |
| `livekit_agent/src/sip_api.py` | ~240 | REST API: CRUD endpoints for agent management |
| `livekit_agent/src/webhook_api.py` | ~320 | Webhook: receives LiveKit events, stores call records, reads transcripts |
| `livekit_agent/src/sip_api_server.py` | ~50 | Server: FastAPI app with CORS, mounts both routers |
| `livekit_agent/src/agent.py` | ~130 | Agent: voice pipeline + transcript capture → Redis |
| `livekit_agent/Dockerfile.sip` | ~37 | Docker: builds the SIP API container |

### Config Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service definitions, networking, env vars |
| `sip.yaml` | LiveKit SIP gateway config |
| `.env` | API keys (DEEPGRAM, OPENAI, ELEVENLABS, etc.) |

### Dependencies (Python)

```
livekit-agents[silero,turn-detector,openai,deepgram,elevenlabs,groq]~=1.4
redis>=4.0
fastapi>=0.100
uvicorn>=0.23
```

---

## Quick Start (for testing)

```bash
# 1. Start all services
docker compose up --build -d

# 2. Register a phone number
curl -X POST http://localhost:8089/sip/agents \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "test-agent",
    "local_number": "09643234042",
    "sip_number": "12707768622",
    "system_prompt": "You are a helpful assistant.",
    "stt": "deepgram",
    "llm": "google",
    "tts": "elevenlabs"
  }'

# 3. Call the SIP number from a phone

# 4. After the call, check the transcript in sip_api logs:
docker logs <sip_api_container_id>

# 5. Or read from Redis directly:
docker exec -it <redis_container_id> redis-cli
> GET call:test-agent:sip-default_-test-agent-*
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Trunk already exists" | SIP number already registered | Delete the existing agent first, or use a different number |
| "flood" in livekit-sip logs | Too many failed call attempts | Restart `livekit-sip` container to clear flood state |
| "connection refused" in livekit-sip | Wrong LiveKit server IP in `sip.yaml` | Use `localhost:7880` if livekit-sip is `network_mode: host` |
| No webhook events | LiveKit not configured to send webhooks | Set `LIVEKIT_CONFIG` env var with webhook URLs |
| Webhook 401 | Wrong API key/secret in SIP API | Ensure `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` match LiveKit server |
| No transcript in call record | Agent process closed before writing | The webhook retries 3 times with 2s delay; check agent logs |
| "not authenticated" in agent logs | Noise cancellation plugin auth issue | Harmless warning — doesn't affect functionality |
