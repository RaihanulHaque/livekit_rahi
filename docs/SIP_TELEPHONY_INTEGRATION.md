# SIP Telephony Integration Guide

Complete technical reference for integrating the SIP telephony backend into your production SaaS.

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
13. [Split-Server Deployment](#split-server-deployment)
14. [File Reference](#file-reference)

---

## Architecture Overview

### Production Architecture (Recommended)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Server A — Your SaaS                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  SaaS Backend (FastAPI / any framework)                       │   │
│  │                                                               │   │
│  │  - sip_manager.py  ← merged in, calls LiveKit API directly   │   │
│  │  - sip_api.py      ← CRUD routes for agent/number mgmt       │   │
│  │  - webhook_api.py  ← receives LiveKit events + transcripts    │   │
│  │                                                               │   │
│  │  On call end → POSTs transcript to your own DB endpoint       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ LiveKit API (gRPC/HTTPS)
                             │ + Webhook callbacks (HTTPS)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Server B — LiveKit Stack                      │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐    │
│  │  LiveKit      │   │  Redis       │   │  LiveKit Agent       │    │
│  │  Server:7880  │◄──│  :6379       │   │  Worker(s)           │    │
│  └──────┬───────┘   └──────────────┘   │  - STT/LLM/TTS       │    │
│         │                              │  - captures transcript│    │
│         │                              │  - writes to Redis    │    │
│  ┌──────┴───────┐                      └──────────────────────┘    │
│  │  LiveKit SIP  │                                                   │
│  │  :5060        │                                                   │
│  └──────────────┘                                                   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │ SIP INVITE
                      ┌──────┴──────┐
                      │ SIP Provider │
                      │ (Telnyx,    │
                      │  Twilio...) │
                      └─────────────┘
                             ▲
                             │ PSTN
                        ☎ Caller
```

### Key Design Decisions

- **`sip_manager.py` merged into SaaS backend** — no separate `sip_api:8089` service. It talks directly to LiveKit Server via LiveKit API SDK.
- **Webhook endpoint lives in SaaS backend** — LiveKit Server POSTs events to your backend's public URL.
- **Transcript delivery** — agent writes transcript to Redis on session close, webhook handler reads it and POSTs to your SaaS DB endpoint via `CALLBACK_WEBHOOK_URL`.
- **Agent config is stateless** — `system_prompt`, `stt`, `llm`, `tts` embedded in LiveKit dispatch rule metadata. Agent reads it on each call. No DB query per call.

---

## Services & What to Deploy

### Server B (LiveKit Stack) — standalone compose

| Service | Required | Notes |
|---------|----------|-------|
| `livekit` | Yes | WebRTC server. Self-host or LiveKit Cloud |
| `livekit-sip` | Yes | SIP gateway. Self-host only |
| `redis` | Yes | Required by LiveKit + agent transcript staging |
| `livekit_agent` | Yes | Voice agent worker(s) |

### Server A (Your SaaS) — merged in

| Code | Required | Notes |
|------|----------|-------|
| `sip_manager.py` | Yes | Copy into your backend |
| `sip_api.py` | Yes | Mount routes in your FastAPI app |
| `webhook_api.py` | Yes | Mount routes in your FastAPI app |
| `sip_api_server.py` | No | Only needed for standalone dev. Not for production |
| `Dockerfile.sip` | No | Dev only. Your SaaS has its own Dockerfile |

---

## SIP API Reference

In production, these routes are mounted inside your SaaS backend. In dev, they run standalone on port 8089.

All endpoints accept `Authorization: Bearer <JWT>` — replace the placeholder validator with your own auth.

### POST /sip/agents — Register Agent with Phone Number

Creates LiveKit SIP inbound trunk + dispatch rule. Stores mapping in Redis.

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

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Your DB agent ID |
| `local_number` | string | User-facing number (e.g. BD local number) |
| `sip_number` | string | SIP provider number (from Telnyx/Twilio) |
| `system_prompt` | string | Voice agent instructions — read from your DB |
| `stt` | string | `deepgram` or `whisper` |
| `llm` | string | `langchain`, `openai`, `groq`, `google` |
| `tts` | string | `elevenlabs`, `openai`, `kokoro` |

**Response (201):**
```json
{
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "trunk_id": "ST_uPnychpk7fPF",
  "dispatch_rule_id": "SDR_QdxFzE5ckwNS",
  "system_prompt": "...",
  "stt": "deepgram",
  "llm": "google",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

**How your SaaS calls this:**
```python
# User assigns number to agent in SaaS UI
agent = db.get_agent(agent_id)
sip_manager.register_agent(
    user_id=current_user.id,
    agent_id=str(agent.id),
    local_number=request.local_number,
    sip_number=request.sip_number,
    system_prompt=agent.system_prompt,   # from your DB
    stt=agent.stt_provider,              # from your DB
    llm=agent.llm_provider,              # from your DB
    tts=agent.tts_provider,              # from your DB
)
```

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

**Response (200):** Full agent config (same shape as register response).

### PATCH /sip/agents/{agent_id} — Update Agent Config

Call this when user updates agent settings in SaaS. Updates the LiveKit dispatch rule so the next call uses the new config.

**Request:**
```json
{
  "system_prompt": "Updated prompt...",
  "tts": "openai"
}
```

**Response (200):** Full updated agent config.

### DELETE /sip/agents/{agent_id} — Delete Agent

Removes dispatch rule, frees number, deletes Redis record. Trunk NOT deleted (provider numbers are reusable).

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

**Endpoint:** `POST /webhook` (in your SaaS backend)

LiveKit Server POSTs events here. Configure in LiveKit Server via `LIVEKIT_CONFIG`:

```yaml
webhook:
  api_key: <your-livekit-api-key>
  urls:
    - https://api.your-saas.com/webhook   # public URL of your SaaS backend
```

### Events Handled

| Event | What Happens |
|-------|-------------|
| `room_started` | Creates call record in Redis (`status: active`) |
| `participant_joined` | Appends to `participants_joined[]` in Redis |
| `participant_left` | Appends to `participants_left[]` in Redis |
| `room_finished` | Computes duration, reads transcript from Redis, POSTs full record to `CALLBACK_WEBHOOK_URL` |
| `participant_connection_aborted` | Sets `status: aborted` in Redis |

### What `room_finished` POSTs to your backend

When a call ends, `webhook_api.py` POSTs this to `{CALLBACK_WEBHOOK_URL}/api/call-completed`:

```json
{
  "agent_id": "car-dealer-1",
  "room_name": "sip-default_-car-dealer-1-_12707768622_xMUZ",
  "local_number": "09643234042",
  "sip_number": "12707768622",
  "duration_seconds": 60,
  "status": "completed",
  "transcript": [
    {"role": "user", "content": "Hi, I want to look at cars", "total_tokens": 0},
    {"role": "assistant", "content": "Welcome! What are you looking for?", "total_tokens": 0},
    {"role": "user", "content": "The Helix, is it good?", "total_tokens": 0},
    {"role": "assistant", "content": "Great choice! The Helix is...", "total_tokens": 0}
  ]
}
```

Your SaaS backend receives this at `/api/call-completed` and saves to your DB.

### Participant Kind Values

| Kind | Meaning |
|------|---------|
| `3` | SIP participant (phone caller) |
| `4` | Agent participant (voice AI) |

---

## Data Flow: Registering a Phone Number

```
SaaS Frontend            SaaS Backend (Server A)         LiveKit Server (Server B)      Redis (Server B)
     │                          │                                  │                          │
     │  Assign agent X          │                                  │                          │
     │  to number 09643234042   │                                  │                          │
     │─────────────────────────►│                                  │                          │
     │                          │  Read agent from DB:             │                          │
     │                          │  {system_prompt, stt, llm, tts} │                          │
     │                          │                                  │                          │
     │                          │  sip_manager.register_agent()    │                          │
     │                          │  create_sip_inbound_trunk()      │                          │
     │                          │─────────────────────────────────►│                          │
     │                          │  trunk_id ◄─────────────────────│                          │
     │                          │                                  │                          │
     │                          │  create_sip_dispatch_rule()      │                          │
     │                          │  room_config.metadata = {        │                          │
     │                          │    system_prompt, stt, llm,      │                          │
     │                          │    tts, agent_id, ...            │                          │
     │                          │  }                               │                          │
     │                          │─────────────────────────────────►│                          │
     │                          │  dispatch_rule_id ◄─────────────│                          │
     │                          │                                  │                          │
     │                          │  SET agent:{user_id}:{agent_id}  │                          │
     │                          │──────────────────────────────────────────────────────────►  │
     │                          │                                  │                          │
     │  ◄─ {trunk_id,           │                                  │                          │
     │      dispatch_rule_id}   │                                  │                          │
```

**Key point:** `system_prompt` and provider config are embedded in the dispatch rule's `room_config.metadata`. Agent reads this on every call — no DB query needed at call time.

---

## Data Flow: Incoming Call Lifecycle

```
☎ Caller    SIP Provider    LiveKit SIP    LiveKit Server    Agent Worker    Redis (B)    SaaS Backend (A)
    │             │               │               │                │              │               │
    │  Dial       │               │               │                │              │               │
    │────────────►│               │               │                │              │               │
    │             │  INVITE       │               │                │              │               │
    │             │──────────────►│               │                │              │               │
    │             │               │  match trunk  │                │              │               │
    │             │               │  match rule   │                │              │               │
    │             │               │  create room  │                │              │               │
    │             │               │  with metadata│                │              │               │
    │             │               │──────────────►│                │              │               │
    │             │               │               │  Webhook:      │              │               │
    │             │               │               │  room_started  │              │               │
    │             │               │               │──────────────────────────────────────────────►│
    │             │               │               │                │              │  store call    │
    │             │               │               │                │              │◄──record───── │
    │             │               │               │  dispatch job  │              │               │
    │             │               │               │───────────────►│              │               │
    │             │               │               │                │  read room   │               │
    │             │               │               │                │  metadata    │               │
    │             │               │               │                │  (system_    │               │
    │             │               │               │                │   prompt,    │               │
    │             │               │               │                │   stt/llm/   │               │
    │             │               │               │                │   tts)       │               │
    │◄════════════════════════════════════════════════════════════►│              │               │
    │              Voice conversation (STT → LLM → TTS)            │              │               │
    │              Transcript captured per turn                     │              │               │
    │             │               │               │                │              │               │
    │  Hang up    │               │               │                │              │               │
    │────────────►│  BYE          │               │                │              │               │
    │             │──────────────►│               │                │              │               │
    │             │               │               │  session close │              │               │
    │             │               │               │◄───────────────│              │               │
    │             │               │               │                │  write       │               │
    │             │               │               │                │  transcript  │               │
    │             │               │               │                │─────────────►│               │
    │             │               │               │  Webhook:      │              │               │
    │             │               │               │  room_finished │              │               │
    │             │               │               │──────────────────────────────────────────────►│
    │             │               │               │                │              │  read record  │
    │             │               │               │                │              │◄──+transcript─│
    │             │               │               │                │              │               │
    │             │               │               │                │              │  POST         │
    │             │               │               │                │              │  /api/call-   │
    │             │               │               │                │              │  completed    │
    │             │               │               │                │              │──────────────►│
    │             │               │               │                │              │  save to DB   │
    │             │               │               │                │              │               │
```

---

## Data Flow: Transcript & Call Record

### How transcripts are captured

1. **During call** — agent process listens to two SDK events:
   - `user_input_transcribed` → `{"role": "user", "content": "...", "total_tokens": 0}`
   - `conversation_item_added` (assistant role only) → `{"role": "assistant", "content": "...", "total_tokens": 0}`

2. **On session close** — agent writes full transcript to Redis: `call:{agent_id}:{room_name}`

3. **On `room_finished` webhook** — webhook handler reads Redis record (retries 3× with 2s delay to wait for transcript), then POSTs full payload to `CALLBACK_WEBHOOK_URL/api/call-completed`

### Transcript format (what your SaaS DB endpoint receives)

```json
[
  {"role": "user", "content": "Hi, I need help", "total_tokens": 0},
  {"role": "assistant", "content": "Hello! How can I help?", "total_tokens": 0},
  {"role": "user", "content": "What's the price?", "total_tokens": 0},
  {"role": "assistant", "content": "The price is $25,000", "total_tokens": 0}
]
```

**Notes:**
- `total_tokens` is always `0` for SIP calls — token counting not available at agent level
- Web-based calls (via frontend) can include real token counts
- Transcript is chronologically ordered — user/assistant interleaved

---

## Redis Schema

Redis on Server B is used for:
1. LiveKit Server's own state (rooms, participants)
2. SIP agent configs (written by SaaS backend via SIPManager)
3. Call records + transcripts (written by webhook + agent, temporary staging)

### Agent Config

```
Key:   agent:{user_id}:{agent_id}
TTL:   None (permanent until deleted via API)
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

### SIP Number Ownership

```
Key:   sip:{user_id}:{sip_number}:owner
TTL:   None
Value: "car-dealer-1"
```

### Call Record (temporary staging, 30-day TTL)

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
  "participants_joined": [
    {"identity": "sip_12707768622", "kind": "3", "joined_at": 1712973601},
    {"identity": "agent-AJ_xyz", "kind": "4", "joined_at": 1712973602}
  ],
  "participants_left": [
    {"identity": "sip_12707768622", "left_at": 1712973658},
    {"identity": "agent-AJ_xyz", "left_at": 1712973659}
  ],
  "transcript": [
    {"role": "user", "content": "...", "total_tokens": 0},
    {"role": "assistant", "content": "...", "total_tokens": 0}
  ]
}
```

**Call records in Redis are staging only** — the authoritative store is your SaaS DB, populated via the `CALLBACK_WEBHOOK_URL` callback.

---

## Integration with Production Backend

### What to copy into your SaaS backend

| File | Modify? | Notes |
|------|---------|-------|
| `sip_manager.py` | No | Core logic — use as-is |
| `sip_api.py` | Yes | Replace JWT validation with your auth |
| `webhook_api.py` | Yes | Set `CALLBACK_WEBHOOK_URL` to your DB endpoint |
| `sip_api_server.py` | No | Dev only — don't copy to production |

### Mount in existing FastAPI app

```python
from sip_api import router as sip_router
from webhook_api import router as webhook_router

app.include_router(sip_router)       # /sip/agents/*
app.include_router(webhook_router)    # /webhook
```

### Replace JWT auth

```python
# sip_api.py — replace validate_jwt:
async def validate_jwt(request: Request) -> dict:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    user = await your_auth_service.verify(token)
    return {"user_id": str(user.id), "token": token}
```

### Connect SIPManager to Server B

```python
# Wherever you initialize SIPManager in your SaaS:
manager = SIPManager(
    livekit_url="ws://server-b-ip:7880",       # or LiveKit Cloud URL
    livekit_api_key=settings.LIVEKIT_API_KEY,
    livekit_api_secret=settings.LIVEKIT_API_SECRET,
    redis_host="server-b-ip",                  # Redis on Server B
    redis_port=6379,
)
```

### Implement the callback endpoint in your SaaS

```python
# Your SaaS backend — receives call records after every call ends
@router.post("/api/call-completed")
async def call_completed(payload: dict):
    agent_id = payload["agent_id"]
    transcript = payload["transcript"]
    duration = payload["duration_seconds"]
    status = payload["status"]

    # Save to your DB
    await db.create_call_record(
        agent_id=agent_id,
        duration_seconds=duration,
        status=status,
        transcript=transcript,
        local_number=payload["local_number"],
        sip_number=payload["sip_number"],
    )
```

### System prompt flow (UI → call)

```
User opens SaaS UI
  → selects agent (has system_prompt, stt, llm, tts in your DB)
  → enters phone number to assign
  → clicks "Assign"

SaaS Backend:
  → reads agent from DB
  → calls sip_manager.register_agent(system_prompt=agent.system_prompt, ...)
  → SIPManager creates dispatch rule in LiveKit with metadata

When call comes in:
  → LiveKit creates room using dispatch rule metadata
  → Agent reads room.metadata → uses system_prompt, stt, llm, tts
  → No DB query at call time
```

When user updates agent in SaaS:
```
SaaS Backend → sip_manager.update_agent(agent_id, system_prompt=new_prompt)
→ Updates LiveKit dispatch rule
→ Next call uses new prompt immediately
```

---

## Frontend Integration

The SIP feature is **backend-to-backend** — frontend only manages assignment UI and call history display.

### What the frontend team needs to build

| UI | API Call (to SaaS Backend) |
|----|---------------------------|
| Assign phone number to agent | `POST /api/agents/{id}/phone` |
| View assigned number | `GET /api/agents/{id}/phone` |
| Update agent config | `PATCH /api/agents/{id}` (existing agent update) |
| Unassign number | `DELETE /api/agents/{id}/phone` |
| View call history | `GET /api/agents/{id}/calls` |
| View transcript | `GET /api/calls/{id}/transcript` |

**Frontend never calls SIP API directly.** SaaS backend owns all SIP operations.

### Web vs SIP comparison

| Aspect | Web (existing) | SIP (this integration) |
|--------|---------------|----------------------|
| Connection | Browser → LiveKit SDK | Phone → SIP provider → LiveKit SIP |
| Agent config source | Frontend sends via JWT metadata | Dispatch rule metadata (set at registration) |
| Transcript | Frontend captures from LLM/TTS | Agent captures via SDK events → Redis → callback |
| Token counts | Available | `total_tokens: 0` (not available) |
| Provider selection | User picks per session | Fixed at registration, updatable via PATCH |

---

## Environment Variables

### SaaS Backend (Server A)

| Variable | Required | Description |
|----------|----------|-------------|
| `LIVEKIT_URL` | Yes | LiveKit Server URL — `ws://server-b-ip:7880` |
| `LIVEKIT_API_KEY` | Yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | Yes | LiveKit API secret |
| `REDIS_HOST` | Yes | Redis on Server B |
| `REDIS_PORT` | Yes | Default `6379` |
| `CALLBACK_WEBHOOK_URL` | Yes | Your SaaS backend base URL — `https://api.your-saas.com` |

### LiveKit Server (Server B) — `LIVEKIT_CONFIG`

```yaml
webhook:
  api_key: <your-livekit-api-key>
  urls:
    - https://api.your-saas.com/webhook    # Server A public URL
```

### LiveKit SIP (Server B) — `sip.yaml`

```yaml
api_key: <your-livekit-api-key>
api_secret: <your-livekit-api-secret>
ws_url: ws://localhost:7880        # localhost if network_mode: host
redis:
  address: localhost:6379          # localhost if network_mode: host
sip_port: 5060
rtp_port: 10000-10100
external_ip: <server-b-public-ip>
```

---

## Split-Server Deployment

### Webhook URL

LiveKit Server (B) must reach your SaaS backend (A) to deliver events:

```yaml
# LIVEKIT_CONFIG on Server B:
webhook:
  api_key: devkey
  urls:
    - https://api.your-saas.com/webhook   # public HTTPS URL
```

No Docker service names across servers — use public URL or private network IP.

### SIPManager connection

SaaS backend (A) calls LiveKit API on Server B:

```
LIVEKIT_URL=ws://server-b-ip:7880
REDIS_HOST=server-b-ip
```

Server B must have ports `7880` (LiveKit) and `6379` (Redis) accessible from Server A (firewall/VPC rules).

### Transcript flow (split-server)

```
Agent (Server B) → writes transcript to Redis (Server B)
LiveKit (Server B) → POST /webhook → SaaS Backend (Server A)
SaaS Backend (Server A) → reads from Redis (Server B) → POSTs to own DB endpoint
```

Redis must be reachable from Server A for the webhook handler to read transcripts.

**Alternative (simpler):** Have the agent POST transcript directly to SaaS backend, skip Redis read in webhook. Requires agent to know `CALLBACK_WEBHOOK_URL`.

---

## Scaling & Multi-Worker

### Agent workers scale horizontally

```bash
docker compose up --scale livekit_agent=3
```

- Each container = one worker
- Each room = one forked process (isolated memory)
- All workers write to same Redis — no shared state issues
- LiveKit auto-distributes jobs across workers

### SIP API / webhook endpoint

- Stateless — all state in Redis
- Scale horizontally behind load balancer
- Update `LIVEKIT_CONFIG` webhook URL to load balancer address

### Redis

- Single instance fine for most loads
- For HA: Redis Sentinel or Redis Cluster
- Call records have 30-day TTL — no unbounded growth

---

## File Reference

| File | Purpose |
|------|---------|
| `livekit_agent/src/sip_manager.py` | Core: creates/deletes LiveKit SIP trunks + dispatch rules |
| `livekit_agent/src/sip_api.py` | REST: CRUD endpoints for agent/number management |
| `livekit_agent/src/webhook_api.py` | Webhook: receives LiveKit events, stages in Redis, POSTs to SaaS |
| `livekit_agent/src/agent.py` | Agent: voice pipeline + transcript capture → Redis |
| `livekit_agent/src/sip_api_server.py` | Dev server only — not for production |
| `livekit_agent/Dockerfile.sip` | Dev only |
| `docker-compose.yml` | Full local dev stack |
| `sip.yaml` | LiveKit SIP gateway config |

### Python dependencies (for SaaS backend)

```
livekit-agents~=1.4
redis>=4.0
fastapi>=0.100
httpx>=0.27      # for CALLBACK_WEBHOOK_URL POST
```

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `"flood"` in livekit-sip logs | Too many failed attempts | Restart `livekit-sip` to clear in-memory state |
| `"connection refused"` in livekit-sip | Wrong LiveKit URL in `sip.yaml` | Use `localhost:7880` if `network_mode: host` |
| No webhook events received | LiveKit not configured to POST | Check `LIVEKIT_CONFIG` webhook URL + API key |
| Webhook 401 | API key mismatch | `LIVEKIT_API_KEY` in SaaS must match LiveKit Server's key |
| No transcript in callback | Agent closed before writing | Webhook retries 3× with 2s delay; check agent logs |
| Callback not firing | `CALLBACK_WEBHOOK_URL` not set | Add to env; empty = disabled |
| `"Trunk already exists"` | Number already registered | Delete agent first or use different SIP number |
| `"not authenticated"` in agent logs | Noise cancellation plugin warning | Harmless — does not affect call functionality |
