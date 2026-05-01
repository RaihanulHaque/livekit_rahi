# Cloud Voice AI — Full System Documentation

Complete end-to-end technical reference. Every flow explained line by line.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Services & Infrastructure](#2-services--infrastructure)
3. [Environment Variables](#3-environment-variables)
4. [Project File Map](#4-project-file-map)
5. [Web Call Flow — Step by Step](#5-web-call-flow--step-by-step)
6. [Agent ID Flow (SaaS Prompt Fetch)](#6-agent-id-flow-saas-prompt-fetch)
7. [Python Agent Internals](#7-python-agent-internals)
8. [Pipeline: STT / LLM / TTS Providers](#8-pipeline-stt--llm--tts-providers)
9. [LangGraph Agent (LangChain LLM)](#9-langgraph-agent-langchain-llm)
10. [Transcript Capture & Call Record](#10-transcript-capture--call-record)
11. [SIP Telephony Flow](#11-sip-telephony-flow)
12. [SIP Manager — Number Provisioning](#12-sip-manager--number-provisioning)
13. [SIP API (REST Endpoints)](#13-sip-api-rest-endpoints)
14. [SIP API Proxy (Next.js)](#14-sip-api-proxy-nextjs)
15. [Webhook API — LiveKit Events](#15-webhook-api--livekit-events)
16. [Redis Schema](#16-redis-schema)
17. [Production Integration Guide](#17-production-integration-guide)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. System Overview

This is a real-time voice AI system. Users speak into a browser (or call a phone number), the system runs speech-to-text → large language model → text-to-speech, and streams audio back.

**Two entry points for calls:**
- **Web**: Browser connects via LiveKit WebRTC. User picks providers and system prompt in the UI.
- **SIP (telephony)**: Someone dials a phone number. Call routes via a SIP provider → LiveKit SIP gateway → same Python agent.

**Key design principle:** All per-session configuration (which STT/LLM/TTS to use, what system prompt) travels inside LiveKit room metadata. The Python agent has zero DB calls at runtime for the web path. Everything is stateless.

---

## 2. Services & Infrastructure

```
docker-compose.yml services:

┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│  frontend   │  │   livekit   │  │   redis     │  │ livekit-sip │  │ livekit_agent│
│  Next.js    │  │  WebRTC srv │  │  state store│  │ SIP gateway │  │  Python AI   │
│  port 3033  │  │  port 7880  │  │  port 6379  │  │  port 5060  │  │  worker      │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘
```

| Service | Purpose | Required |
|---------|---------|---------|
| `frontend` | Next.js web UI, API routes for token generation | Yes |
| `livekit` | WebRTC server — manages rooms and participants | Yes |
| `redis` | LiveKit state + transcript staging + SIP configs | Yes |
| `livekit-sip` | SIP gateway — accepts inbound phone calls | Only for telephony |
| `livekit_agent` | Python agent — runs STT+LLM+TTS pipeline | Yes |

**Dev compose** (`docker-compose.dev.yml`) runs only `livekit`, `livekit_agent`, and `frontend` — no SIP, no Redis (lighter build, no GPU deps).

---

## 3. Environment Variables

Copy `.env.example` → `.env` before starting.

### Required

| Variable | Used By | Purpose |
|----------|---------|---------|
| `LIVEKIT_URL` | agent, compose | WebSocket URL of LiveKit server (`ws://livekit:7880` inside Docker) |
| `LIVEKIT_API_KEY` | frontend, agent | Issued JWT identifier — effectively public |
| `LIVEKIT_API_SECRET` | frontend, agent | HMAC signing key — **must stay private** |
| `DEEPGRAM_API_KEY` | agent | Deepgram STT |
| `OPENAI_API_KEY` | agent | OpenAI LLM + TTS + Whisper STT |
| `ELEVENLABS_API_KEY` | agent | ElevenLabs TTS |
| `NEXT_PUBLIC_LIVEKIT_URL` | frontend browser | Browser-accessible LiveKit URL (`ws://localhost:7880` locally) |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | — | Groq LLM |
| `GEMINI_API_KEY` | — | Google Gemini LLM + TTS |
| `TAVILY_API_KEY` | — | Web search tool in LangGraph agent |
| `DEEPGRAM_MODEL` | `flux-general-en` | Deepgram model name |
| `DEEPGRAM_EAGER_EOT_THRESHOLD` | `0.4` | End-of-turn detection sensitivity |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `TTS_MODEL` | `eleven_v3` | ElevenLabs model |
| `TTS_VOICE_ID` | `Gvx1qZk9R4BUiBfsNPBU` | ElevenLabs voice |
| `TTS_LANGUAGE` | `bn` (for eleven_v3) | TTS language code |
| `SAAS_BACKEND_URL` | — | URL to fetch system prompts by agent_id |
| `CALLBACK_WEBHOOK_URL` | — | URL to POST call records to on call end |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `SIP_API_BASE` | `http://localhost:8089` | SIP API base URL (used by Next.js proxy) |

**Security note:** `LIVEKIT_API_KEY` appears inside every JWT (base64, readable). `LIVEKIT_API_SECRET` signs the JWT — anyone who knows it can forge tokens. Never commit it.

---

## 4. Project File Map

```
.
├── frontend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── connection-details/route.ts   ← JWT generation + room metadata embedding
│   │   │   ├── system-prompt/route.ts        ← demo agent profile lookup (hvac/sales/support)
│   │   │   └── sip/[[...path]]/route.ts      ← proxy: forwards /api/sip/* → sip_api:8089
│   │   └── page.tsx                          ← root page, renders <App />
│   ├── components/app/
│   │   ├── app.tsx                           ← top-level state: model selections, token fetch
│   │   ├── welcome-view.tsx                  ← UI: STT/LLM/TTS dropdowns + prompt input
│   │   ├── session-view.tsx                  ← UI: active call view
│   │   ├── sip-management-view.tsx           ← UI: SIP phone number management panel
│   │   └── view-controller.tsx              ← switches between welcome/session/sip views
│   └── app-config.ts                        ← title, feature flags (chat/video/screenshare)
│
├── livekit_agent/
│   └── src/
│       ├── agent.py           ← ENTRYPOINT: prewarm VAD, handle session, capture transcript
│       ├── assistant.py       ← Agent subclass: default instructions, on_enter greeting
│       ├── pipeline.py        ← build_session(): assembles STT+LLM+TTS from config dict
│       ├── langgraph_agent.py ← LangGraph workflow with tools (calculator, weather, Tavily)
│       ├── sip_manager.py     ← SIPManager: create/delete/update LiveKit trunks + dispatch rules
│       ├── sip_api.py         ← FastAPI router: /sip/agents CRUD, runs on port 8089
│       ├── sip_api_server.py  ← Standalone dev server wrapping sip_api.py (dev only)
│       ├── webhook_api.py     ← FastAPI router: /webhook, handles LiveKit lifecycle events
│       └── system_prompt.py   ← legacy static HVAC prompt (reference only)
│
├── test-back.py               ← local SaaS backend simulator (port 8083)
├── docker-compose.yml         ← production stack
├── docker-compose.dev.yml     ← dev stack (faster, no GPU/SIP/Redis)
├── sip.yaml                   ← livekit-sip container config
├── .env.example
└── CLAUDE.md                  ← AI coding assistant instructions
```

---

## 5. Web Call Flow — Step by Step

This is the primary path. Every line explained.

### Step 1 — User opens the browser

```
Browser → GET http://localhost:3033
        → Next.js serves the React app
        → welcome-view.tsx renders:
            - STT dropdown (deepgram | whisper | elevenlabs)
            - LLM dropdown (langchain | openai | groq | google)
            - TTS dropdown (elevenlabs | openai | kokoro | google)
            - Mode toggle: [Custom Prompt] [Agent ID]
            - Prompt textarea or Agent ID input field
```

Nothing connects to LiveKit yet.

### Step 2 — User clicks "Start Call"

`frontend/components/app/app.tsx` POSTs to `/api/connection-details`:

```json
POST /api/connection-details
{
  "stt": "deepgram",
  "llm": "langchain",
  "tts": "elevenlabs",

  // Custom Prompt mode:
  "system_prompt": "You are an HVAC support agent...",

  // OR Agent ID mode:
  "agent_id": "2008011"
}
```

### Step 3 — connection-details/route.ts generates the LiveKit JWT

File: `frontend/app/api/connection-details/route.ts`

```typescript
// Line 33: Parse the POST body
const body = await req.json().catch(() => ({}));

// Line 38-39: Generate random participant + room identifiers
const participantIdentity = `voice_assistant_user_${Math.floor(Math.random() * 10_000)}`;
const roomName = `voice_assistant_room_${Math.floor(Math.random() * 10_000)}`;

// Line 41-47: Pack ALL session config into a JSON string — this becomes room metadata
const roomMetadata = JSON.stringify({
  stt:           body?.stt           || 'deepgram',
  llm:           body?.llm           || 'langchain',
  tts:           body?.tts           || 'elevenlabs',
  system_prompt: body?.system_prompt || null,
  agent_id:      body?.agent_id      || null,
});

// Line 49-53: Sign a LiveKit JWT with TTL=15min
// roomConfig.metadata = the JSON string above
const participantToken = await createParticipantToken(
  { identity: participantIdentity, name: 'user' },
  roomName,
  agentName,        // optional named agent dispatch
  roomMetadata
);

// Line 57-63: Return connection details to the browser
return NextResponse.json({
  serverUrl: LIVEKIT_CLIENT_URL,   // ws://localhost:7880
  roomName,
  participantToken,
  participantName: 'user',
});
```

**Why embed in JWT?** The metadata lives server-side inside the signed token. The browser never sees the raw secret, and the agent gets the config automatically when it joins the room. No separate API call needed.

**JWT contents (base64-readable, not encrypted):**
```json
{
  "iss": "LIVEKIT_API_KEY",
  "sub": "voice_assistant_user_1234",
  "exp": 1712973600,
  "video": { "room": "voice_assistant_room_5678", "roomJoin": true, ... },
  "roomConfig": {
    "metadata": "{\"stt\":\"deepgram\",\"llm\":\"langchain\",...}"
  }
}
```

### Step 4 — Browser connects to LiveKit

```
Browser (livekit-client SDK)
  → WebSocket connect → ws://localhost:7880
  → Sends JWT in connection handshake
  → LiveKit Server verifies JWT signature using LIVEKIT_API_SECRET
  → Room "voice_assistant_room_5678" created with metadata attached
  → Browser joins as participant
```

### Step 5 — LiveKit dispatches job to agent

```
LiveKit Server detects new room
  → Finds available livekit_agent worker
  → Sends job to worker
  → my_agent(ctx) is called
```

### Step 6 — Agent joins the room and reads config

File: `livekit_agent/src/agent.py`, function `my_agent(ctx)`

```python
# Line 72: Agent joins the room
await ctx.connect()

# Line 74-76: Parse room metadata JSON
try:
    config = json.loads(ctx.room.metadata or "{}")
except json.JSONDecodeError:
    config = {}

# Line 79-80: Extract fields from config
system_prompt: str | None = config.get("system_prompt") or None
agent_id = config.get("agent_id", "unknown")
```

### Step 7 — Session starts

```python
# Line 134: Build the STT+LLM+TTS pipeline from config
session = build_session(vad=ctx.proc.userdata["vad"], config=config)

# Line 218-224: Start the session with the Agent
await session.start(
    agent=Assistant(instructions=system_prompt),
    room=ctx.room,
    room_options=room_io.RoomOptions(
        audio_input=_build_audio_input_options(),  # noise cancellation
    ),
)
```

`Assistant(instructions=system_prompt)` — if `system_prompt` is None, falls back to `DEFAULT_INSTRUCTIONS` (friendly generic assistant).

### Step 8 — Voice conversation loop

```
User speaks
  → VAD (Silero) detects end of speech
  → STT transcribes audio → text
  → LLM generates response text
  → TTS synthesizes text → audio
  → Audio streamed back to browser via WebRTC
(repeat until call ends)
```

### Step 9 — Call ends

```
User closes tab / clicks end
  → session "close" event fires in agent.py
  → transcript saved to Redis: call:{agent_id}:{room_name}
  → if CALLBACK_WEBHOOK_URL is set:
      POST {CALLBACK_WEBHOOK_URL}/api/v1/call-completed
      body: { agent_id, room_name, transcript, duration_seconds, status }
```

---

## 6. Agent ID Flow (SaaS Prompt Fetch)

When `agent_id` is set in room metadata and `SAAS_BACKEND_URL` is configured, the agent fetches the system prompt from an external backend instead of reading it inline.

**Why this exists:** Embedding large system prompts in the JWT has size limits and exposes prompt text in the token. Agent ID mode keeps the JWT tiny and centralizes prompt management.

### Flow

```python
# agent.py line 88-125

# Only runs if agent_id is present and SAAS_BACKEND_URL is set
if agent_id and agent_id != "unknown":
    saas_url = os.environ.get("SAAS_BACKEND_URL", "").rstrip("/")
    if saas_url:

        # Sign a short-lived JWT (30s TTL) using LIVEKIT_API_KEY + LIVEKIT_API_SECRET
        # This authenticates the agent to the SaaS backend
        auth_token = jwt.encode(
            {"iss": lk_api_key, "exp": int(time.time()) + 30},
            lk_api_secret,
            algorithm="HS256",
        )

        # Fetch system prompt from SaaS backend
        url = f"{saas_url}/api/v1/agents/{agent_id}"
        resp = httpx.get(url, headers={"Authorization": f"Bearer {auth_token}"}, timeout=5)

        if resp.status_code == 200:
            system_prompt = resp.json().get("system_prompt") or None
```

**Auth mechanism:** The SaaS backend already holds `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` (you gave them to it). It verifies the JWT signature using the same secret. No extra credentials needed.

**SaaS backend verification (what `test-back.py` implements):**
```python
# Decode JWT from Authorization header
# Verify HMAC-SHA256 signature using LIVEKIT_API_SECRET
# Check iss == LIVEKIT_API_KEY
# Check token not expired (30s TTL)
# Return { agent_id, name, system_prompt }
```

**Local testing:** Run `python test-back.py` (starts on port 8083) and set:
```bash
SAAS_BACKEND_URL=http://host.docker.internal:8083
```

---

## 7. Python Agent Internals

### Startup: prewarm

```python
# agent.py line 32-36
def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm
```

`prewarm` runs once when the worker process starts (before any room is assigned). It pre-loads the Silero VAD model into memory so the first call doesn't incur cold-start latency. The loaded VAD is stored in `proc.userdata["vad"]` and shared across all sessions in this process.

### Noise Cancellation

```python
# agent.py line 47-63
def _build_audio_input_options() -> room_io.AudioInputOptions:
    try:
        from livekit.plugins import noise_cancellation
    except Exception as exc:
        # Plugin unavailable (e.g., dev build) — continue without it
        return room_io.AudioInputOptions()

    return room_io.AudioInputOptions(
        noise_cancellation=lambda params:
            noise_cancellation.BVCTelephony()   # SIP callers: telephony codec
            if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
            else noise_cancellation.BVC()        # Web callers: wideband
    )
```

Automatically selects the right noise cancellation mode:
- `BVCTelephony` — optimized for 8kHz PSTN audio (SIP callers)
- `BVC` — optimized for 16kHz+ browser audio (web callers)

### Assistant class

File: `livekit_agent/src/assistant.py`

```python
DEFAULT_INSTRUCTIONS = """You are a helpful voice AI assistant..."""

class Assistant(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        # Use provided instructions, or fall back to DEFAULT_INSTRUCTIONS
        super().__init__(instructions=instructions or DEFAULT_INSTRUCTIONS)

    async def on_enter(self) -> None:
        # Called automatically when agent joins the session
        # Generates an opening greeting
        await self.session.generate_reply(
            instructions="Greet the user and offer your assistance.",
            allow_interruptions=True,
        )
```

`on_enter` fires as soon as the session starts. The agent speaks first.

---

## 8. Pipeline: STT / LLM / TTS Providers

File: `livekit_agent/src/pipeline.py`

### build_session()

```python
def build_session(vad, config: dict = None) -> AgentSession:
    return AgentSession(
        stt=build_stt_dynamic(config),     # speech-to-text
        llm=build_llm_dynamic(config),     # language model
        tts=build_tts_dynamic(config),     # text-to-speech
        turn_handling=TurnHandlingOptions(
            turn_detector=MultilingualModel()  # multilingual end-of-turn detection
        ),
        vad=vad,                            # voice activity detection (pre-loaded in prewarm)
        preemptive_generation=True,         # start generating LLM response before STT finalizes
    )
```

`config` is the dict parsed from `ctx.room.metadata`. Keys `stt`, `llm`, `tts` select the provider.

### STT Providers

```python
def build_stt_dynamic(config: dict):
    provider = config.get("stt", "deepgram")  # default: deepgram

    if provider == "deepgram":
        return deepgram.STTv2(
            model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", "flux-general-en")),
            eager_eot_threshold=float(os.getenv("DEEPGRAM_EAGER_EOT_THRESHOLD", "0.4")),
            api_key=...,
        )
    elif provider == "elevenlabs":
        return elevenlabs.STT(model_id="scribe_v2_realtime", language_code="bn", ...)
    elif provider == "whisper":
        return openai.STT(model="whisper-1", ...)
```

| Value | Provider | Notes |
|-------|---------|-------|
| `deepgram` | Deepgram STTv2 | Default. `flux-general-en` model. Eager EOT for responsiveness |
| `elevenlabs` | ElevenLabs Scribe | Real-time, Bengali (`bn`) |
| `whisper` | OpenAI Whisper | Via OpenAI API |

### LLM Providers

```python
def build_llm_dynamic(config: dict):
    provider = config.get("llm", "langchain")  # default: langchain (LangGraph)

    if provider == "openai":
        return openai.LLM(model=os.getenv("LLM_MODEL", "gpt-4o-mini"), ...)
    elif provider == "groq":
        return groq.LLM(model="openai/gpt-oss-120b", ...)
    elif provider == "google":
        return google.LLM(model="gemini-3.1-flash-lite-preview", ...)
    elif provider == "langchain":
        return build_llm_langchain(graph_app)  # LangGraph with tools
```

| Value | Provider | Notes |
|-------|---------|-------|
| `langchain` | LangGraph (LM Studio) | Default. Has tools: calculator, weather, Tavily search |
| `openai` | OpenAI API | `gpt-4o-mini` default |
| `groq` | Groq API | Fast inference |
| `google` | Gemini | `gemini-3.1-flash-lite-preview` |

### TTS Providers

```python
def build_tts_dynamic(config: dict):
    provider = config.get("tts", "elevenlabs")  # default: elevenlabs

    if provider == "elevenlabs":
        model = config.get("tts_model", os.getenv("TTS_MODEL", "eleven_v3"))
        # eleven_v3 doesn't support WebSocket streaming → use HTTP chunked TTS
        cls = ElevenLabsHTTPTTS if model == "eleven_v3" else elevenlabs.TTS
        return cls(voice_id=..., model=model, language="bn", ...)
    elif provider == "google":
        return google_beta.GeminiTTS(model="gemini-3.1-flash-tts-preview", voice_name="Zephyr", ...)
    elif provider == "kokoro":
        return openai.TTS(base_url="http://kokoro:8880/v1", model="kokoro", voice="af_nova", ...)
    elif provider == "openai":
        return openai.TTS(voice="alloy", ...)
```

| Value | Provider | Notes |
|-------|---------|-------|
| `elevenlabs` | ElevenLabs | Default. `eleven_v3` uses HTTP (not WebSocket). TTFB ~0.7s |
| `google` | Gemini TTS | Gemini flash TTS preview |
| `kokoro` | Kokoro (local) | Runs in separate Docker container on port 8880 |
| `openai` | OpenAI TTS | `alloy` voice default |

**ElevenLabsHTTPTTS note:** `eleven_v3` model returns 403 on WebSocket streaming endpoint. The `ElevenLabsHTTPTTS` subclass overrides capabilities to `streaming=False`, forcing the HTTP chunked path. Trade-off: slightly higher TTFB (~0.7s vs ~0.2s) but correct.

### Adding a new provider

1. Add a `elif provider == "your-provider":` case in the relevant `build_*_dynamic()` function in `pipeline.py`
2. Add the option to the `<Select>` dropdown in `frontend/components/app/welcome-view.tsx`
3. No DB changes — selection flows through JWT metadata automatically

---

## 9. LangGraph Agent (LangChain LLM)

File: `livekit_agent/src/langgraph_agent.py`

When LLM provider is `langchain`, the pipeline uses a LangGraph workflow instead of a direct API call.

### Graph structure

```
START → [agent node] → tools_condition →  [tools node]
                     ↓ (no tool call)         ↓
                    END              → [agent node] (loop back)
```

### Tools available

| Tool | Purpose |
|------|---------|
| `calculator(expression)` | Evaluates math expressions via `eval()` |
| `get_weather(location)` | Mock weather (returns hardcoded response) |
| `TavilySearch` | Real web search — only enabled if `TAVILY_API_KEY` is set |

### LLM backend

Defaults to LM Studio running locally at `http://host.docker.internal:1234/v1/`. This is an OpenAI-compatible local inference server. Change to any OpenAI-compatible endpoint by modifying the `base_url`.

### Known limitation

`call_model()` in `langgraph_agent.py` hardcodes its own `SystemMessage`:
```python
system_prompt = SystemMessage(
    content="You are a helpful, conversational voice assistant..."
)
response = llm_with_tools.invoke([system_prompt] + messages)
```

This **ignores** the `instructions` passed to `Assistant()`. When using the `langchain` LLM option, the injected system prompt from room metadata is not applied. The other LLM providers (openai, groq, google) correctly use the injected instructions.

---

## 10. Transcript Capture & Call Record

File: `livekit_agent/src/agent.py`, lines 136–214

### Capturing transcript turns

```python
transcript: list[dict] = []

# Fires on every finalized STT result
@session.on("user_input_transcribed")
def on_user_speech(ev):
    if ev.is_final and ev.transcript.strip():
        transcript.append({
            "role": "user",
            "content": ev.transcript.strip(),
            "total_tokens": 0,
        })

# Fires when assistant generates a text response
@session.on("conversation_item_added")
def on_conversation_item(ev):
    item = ev.item
    text = getattr(item, "text_content", None) or ""
    if not text.strip():
        return
    role = getattr(item, "role", None)
    if role == "assistant":
        transcript.append({
            "role": "assistant",
            "content": text.strip(),
            "total_tokens": 0,
        })
```

### On session close

```python
@session.on("close")
def on_session_close(ev):
    # 1. Save transcript to Redis
    r = _get_redis()
    call_key = f"call:{agent_id}:{room_name}"
    existing = r.get(call_key)

    if existing:
        record = json.loads(existing)    # merge with webhook-written record if exists
    else:
        record = {"room_name": room_name, "agent_id": agent_id}

    record["transcript"] = transcript
    r.set(call_key, json.dumps(record), ex=86400 * 30)  # 30-day TTL

    # 2. POST to SaaS backend callback
    callback_url = os.environ.get("CALLBACK_WEBHOOK_URL", "")
    if callback_url:
        httpx.post(
            f"{callback_url}/api/v1/call-completed",
            json={
                "agent_id": agent_id,
                "room_name": room_name,
                "local_number": local_number,
                "sip_number": sip_number,
                "duration_seconds": max(0, ended_at - started_at),
                "status": "completed",
                "transcript": transcript,
            },
            timeout=10,
        )
```

Transcript format each turn:
```json
{"role": "user", "content": "Hi, I need help", "total_tokens": 0}
{"role": "assistant", "content": "Hello! How can I help you today?", "total_tokens": 0}
```

`total_tokens` is always 0 — token counting not available at the agent SDK level.

---

## 11. SIP Telephony Flow

For phone-based calls. Same Python agent, different entry path.

### Prerequisites

1. A SIP provider (Telnyx, Twilio, etc.) with a phone number
2. SIP provider configured to route calls to your server IP on port 5060
3. `livekit-sip` container running
4. At least one inbound trunk + dispatch rule registered (via `sip_manager.py`)

### Call path

```
Caller dials SIP number (e.g., +12707768622)
  ↓
SIP provider routes INVITE → your server:5060
  ↓
livekit-sip container receives SIP INVITE
  ↓
LiveKit checks: inbound trunk exists for this number?
  YES → proceed
  NO  → reject with 486 "flood"
  ↓
LiveKit checks: dispatch rule exists for this trunk?
  YES → create room with room metadata from dispatch rule
  NO  → reject
  ↓
Room created: "sip-{user_id[:8]}-{agent_id}-{random}"
Room metadata = { agent_id, local_number, sip_number, system_prompt, stt, llm, tts }
  ↓
Python agent dispatched → my_agent(ctx) called
  ↓
agent.py reads ctx.room.metadata (same code path as web calls)
  ↓
build_session() called → voice conversation starts
```

**Key insight:** Web calls and SIP calls use the **same Python agent code**. The only difference is how the room metadata gets populated:
- Web: `connection-details/route.ts` embeds it in the JWT
- SIP: `SIPManager` embeds it in the dispatch rule at registration time

### sip.yaml (livekit-sip config)

```yaml
api_key: devkey
api_secret: secret
ws_url: ws://livekit:7880      # Docker service name (or localhost if network_mode: host)
redis:
  address: redis:6379
sip_port: 5060
rtp_port: 10000-10100          # RTP media ports (must be open in firewall)
use_external_ip: true          # Required for NAT traversal
```

---

## 12. SIP Manager — Number Provisioning

File: `livekit_agent/src/sip_manager.py`

`SIPManager` wraps the LiveKit SIP API to create/manage inbound trunks and dispatch rules.

### register_agent()

```python
async def register_agent(
    self,
    user_id: str,
    agent_id: str,
    local_number: str,   # user-facing number (e.g. "09643234042")
    sip_number: str,     # SIP provider number (e.g. "12707768622") — REQUIRED
    stt: str, llm: str, tts: str,
    system_prompt: Optional[str] = None,
) -> dict:
```

**Step by step:**

1. **Check for existing assignment:** If this agent already has a different number, detach the old one first.
2. **Check number ownership:** If the SIP number is owned by a different agent, detach it from that agent.
3. **Check for existing trunk:** If an inbound trunk already exists for this SIP number, reuse it. Otherwise create a new one.
4. **Create dispatch rule:** Sets `room_config.metadata` with full agent config (same JSON shape as web JWT metadata).
5. **Store in Redis:** `agent:{user_id}:{agent_id}` → full config JSON. `sip:{user_id}:{sip_number}:owner` → `agent_id`.

```python
# Dispatch rule room metadata (same shape as web call metadata):
metadata = {
    "agent_id": agent_id,
    "local_number": local_number,
    "sip_number": sip_number,
    "system_prompt": system_prompt,   # or None if agent fetches from SaaS via agent_id
    "stt": stt,
    "llm": llm,
    "tts": tts,
}

# Room prefix for calls from this agent's number:
room_prefix = f"sip-{user_id[:8]}-{agent_id}-"

# SIPDispatchRuleIndividual: each caller gets their own room
rule = api.SIPDispatchRule(
    dispatch_rule_individual=api.SIPDispatchRuleIndividual(room_prefix=room_prefix)
)
```

`SIPDispatchRuleIndividual` means 100 concurrent callers to the same number = 100 separate rooms, each with their own agent session. No shared state.

### delete_agent()

- Deletes the dispatch rule in LiveKit
- Clears number ownership in Redis
- Removes agent record from Redis
- Does NOT delete the trunk (trunks are tied to provider numbers and reusable)

### update_agent()

- Updates Redis record
- Reads existing dispatch rule from LiveKit
- Creates updated dispatch rule with new metadata
- Next incoming call uses the new config immediately (no restart needed)

### list_agents() / get_agent()

Pure Redis reads. Pattern: `keys("agent:{user_id}:*")`.

---

## 13. SIP API (REST Endpoints)

File: `livekit_agent/src/sip_api.py`

FastAPI router mounted at `/sip`. Runs on port 8089.

All endpoints use `Depends(validate_jwt)` — in dev mode this accepts any request and returns `user_id = "default_user"`. **Replace `validate_jwt` with your real auth before production.**

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/sip/agents` | Register agent with phone number |
| `GET` | `/sip/agents` | List all agents for user |
| `GET` | `/sip/agents/{agent_id}` | Get specific agent config |
| `PATCH` | `/sip/agents/{agent_id}` | Update system prompt / providers |
| `DELETE` | `/sip/agents/{agent_id}` | Delete agent, free number |

### POST /sip/agents — Register

Request body:
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

`system_prompt` can be omitted if you use `agent_id` mode — the Python agent will fetch it from the SaaS backend at call time.

Response (201):
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

### PATCH /sip/agents/{agent_id} — Update

```json
{
  "system_prompt": "Updated prompt...",
  "tts": "openai"
}
```

All fields optional. Only provided fields are updated. Updates the LiveKit dispatch rule immediately — next call uses new config.

### DELETE /sip/agents/{agent_id}

```json
{
  "deleted": true,
  "agent_id": "car-dealer-1",
  "local_number": "09643234042",
  "sip_number": "12707768622"
}
```

---

## 14. SIP API Proxy (Next.js)

File: `frontend/app/api/sip/[[...path]]/route.ts`

The browser and frontend components call `/api/sip/...`. This Next.js route proxies those requests to the Python backend at `sip_api:8089`.

```typescript
const SIP_API_BASE =
  process.env.SIP_API_BASE ||
  (process.env.NODE_ENV === 'production'
    ? 'http://sip_api:8089'     // Docker service name in production
    : 'http://localhost:8089'); // localhost in dev

// Path mapping:
// /api/sip/agents       → http://sip_api:8089/sip/agents
// /api/sip/agents/hvac  → http://sip_api:8089/sip/agents/hvac
```

Forwards `Authorization` header transparently. Handles GET, POST, PATCH, DELETE.

---

## 15. Webhook API — LiveKit Events

File: `livekit_agent/src/webhook_api.py`

LiveKit Server POSTs events to `POST /webhook` when room/participant lifecycle changes. This endpoint tracks call records in Redis.

### Event handlers

| Event | Handler | What it does |
|-------|---------|-------------|
| `room_started` | `_handle_room_started` | Creates call record in Redis with `status: active` |
| `room_finished` | `_handle_room_finished` | Computes duration, reads transcript, POSTs to `CALLBACK_WEBHOOK_URL` |
| `participant_joined` | `_handle_participant_joined` | Appends to `participants_joined[]` list |
| `participant_left` | `_handle_participant_left` | Appends to `participants_left[]` list |
| `participant_connection_aborted` | `_handle_participant_connection_aborted` | Sets `status: aborted` |

### Webhook validation

```python
# webhook_api.py line 46-47
_token_verifier = TokenVerifier(_api_key, _api_secret)
_receiver = WebhookReceiver(_token_verifier)

# line 318-321: On every incoming webhook:
event = _receiver.receive(body.decode("utf-8"), auth_header)
# Raises exception if signature invalid → 401 response
```

LiveKit signs each webhook with the same `LIVEKIT_API_SECRET`. The `WebhookReceiver` verifies the signature before any handler runs.

### room_finished transcript coordination

```python
# webhook_api.py line 139-146
# The agent process writes transcript to Redis on session close.
# room_finished may arrive slightly before or after the agent writes.
# Retry briefly to catch the transcript:
record = None
for attempt in range(3):
    existing = r.get(key)
    if existing:
        record = json.loads(existing)
        if record.get("transcript"):
            break
    if attempt < 2:
        time.sleep(2)  # wait 2s between retries
```

After 3 attempts (up to 4 seconds wait), it proceeds with whatever it has.

### Callback to production backend

```python
# webhook_api.py line 172-190
callback_url = os.environ.get("CALLBACK_WEBHOOK_URL", "")
if callback_url:
    httpx.post(
        f"{callback_url}/api/call-completed",
        json={
            "agent_id": agent_id,
            "room_name": room_name,
            "local_number": local_number,
            "sip_number": sip_number,
            "duration_seconds": duration_seconds,
            "status": "completed",
            "transcript": transcript,    # full turn-by-turn array
        },
        timeout=10,
    )
```

Note: `agent.py` also POSTs to `CALLBACK_WEBHOOK_URL/api/v1/call-completed` (note `/v1/` in path). `webhook_api.py` POSTs to `CALLBACK_WEBHOOK_URL/api/call-completed` (no `/v1/`). These are different paths — make sure your backend handles both, or set only one of the two delivery mechanisms.

### Configure LiveKit to deliver webhooks

In `LIVEKIT_CONFIG` (LiveKit Server config):
```yaml
webhook:
  api_key: your-livekit-api-key
  urls:
    - https://api.your-saas.com/webhook   # must be public HTTPS
```

In dev, if livekit_agent is running in Docker alongside LiveKit, you can use the Docker service name: `http://livekit_agent:8089/webhook`.

---

## 16. Redis Schema

All keys used by this system:

### SIP Agent Config (permanent until deleted)

```
Key:   agent:{user_id}:{agent_id}
TTL:   None
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
Value: "car-dealer-1"    (the agent_id that owns this number)
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
  "status": "completed",      // active | completed | aborted
  "participants_joined": [
    {"identity": "sip_12707768622", "kind": "3", "joined_at": 1712973601},
    {"identity": "agent-AJ_xyz",    "kind": "4", "joined_at": 1712973602}
  ],
  "participants_left": [
    {"identity": "sip_12707768622", "left_at": 1712973658}
  ],
  "transcript": [
    {"role": "user",      "content": "Hi",        "total_tokens": 0},
    {"role": "assistant", "content": "Hello!",    "total_tokens": 0}
  ]
}
```

Participant kind values: `3` = SIP caller, `4` = AI agent worker.

Call records are staging only — the authoritative store is your SaaS DB, populated via `CALLBACK_WEBHOOK_URL`.

---

## 17. Production Integration Guide

### What to deploy

**Server B — LiveKit Stack (standalone):**
- `livekit` container
- `livekit-sip` container
- `redis` container
- `livekit_agent` container(s)

**Server A — Your SaaS backend:**
Copy these files from `livekit_agent/src/` into your FastAPI app:

| File | Modify? | Notes |
|------|---------|-------|
| `sip_manager.py` | No | Use as-is |
| `sip_api.py` | Yes | Replace `validate_jwt` with your auth |
| `webhook_api.py` | Yes | Set `CALLBACK_WEBHOOK_URL` env var |

Mount in your FastAPI app:
```python
from sip_api import router as sip_router
from webhook_api import router as webhook_router

app.include_router(sip_router)    # /sip/agents/*
app.include_router(webhook_router) # /webhook
```

### Replace JWT auth in sip_api.py

```python
async def validate_jwt(request: Request) -> dict:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    user = await your_auth_service.verify(token)
    return {"user_id": str(user.id), "token": token}
```

### Connect SIPManager to Server B's LiveKit

```python
manager = SIPManager(
    livekit_url="ws://server-b-ip:7880",
    livekit_api_key=settings.LIVEKIT_API_KEY,
    livekit_api_secret=settings.LIVEKIT_API_SECRET,
    redis_host="server-b-ip",
    redis_port=6379,
)
```

### Implement the callback endpoint on your SaaS

```python
@router.post("/api/call-completed")
async def call_completed(payload: dict):
    await db.create_call_record(
        agent_id=payload["agent_id"],
        duration_seconds=payload["duration_seconds"],
        status=payload["status"],
        transcript=payload["transcript"],
        local_number=payload["local_number"],
        sip_number=payload["sip_number"],
    )
```

### System prompt lifecycle in production

```
User updates agent in SaaS UI
  → SaaS backend reads new system_prompt from DB
  → PATCH /sip/agents/{agent_id}  { system_prompt: "..." }
  → sip_manager.update_agent() updates LiveKit dispatch rule
  → Next call immediately uses new prompt
  → No restart needed
```

### Scaling agent workers

```bash
docker compose up --scale livekit_agent=3
```

Each container = one worker process. LiveKit auto-distributes incoming jobs across workers. Each room runs in an isolated subprocess (forked by LiveKit agents SDK) — no shared state between calls.

### Production checklist

- Replace `--dev` LiveKit mode with real config + strong API key/secret
- Replace `validate_jwt` in `sip_api.py` with real auth
- Replace `test-back.py` with real SaaS backend
- Set `LIVEKIT_CONFIG` webhook URL to your SaaS backend's public URL
- Open firewall ports: 7880 (LiveKit), 5060/udp (SIP), 10000-10100/udp (RTP media)
- Add Redis Sentinel or Cluster for HA (single instance fine for low volume)
- Put secrets in a secrets manager (not plain `.env`)

---

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Agent joins but no voice | Noise cancellation plugin missing | Normal in dev build, check logs for warning |
| `486 flood` in livekit-sip logs | No inbound trunk for phone number | Register agent via `POST /sip/agents` |
| No transcript in call record | Agent closed before writing | Webhook retries 3× with 2s delay; check agent logs |
| LangGraph ignores system prompt | Hardcoded SystemMessage in `call_model()` | Known issue — use `openai`/`groq`/`google` LLM instead |
| `Failed to reach SIP API` | livekit_agent not running on port 8089 | Check container is running; check `SIP_API_BASE` env var |
| `Trunk already exists` | SIP number already registered | DELETE the agent first, or use different SIP number |
| Webhook 401 | API key mismatch | `LIVEKIT_API_KEY` in SaaS must match key in LiveKit Server config |
| No callback firing | `CALLBACK_WEBHOOK_URL` not set | Add to env; empty = callback disabled |
| LM Studio connection refused | LangGraph LLM trying to reach local LM Studio | Switch LLM to `openai`, `groq`, or `google` in the session config |
| ElevenLabs 403 on WebSocket | `eleven_v3` model doesn't support WebSocket | Already handled by `ElevenLabsHTTPTTS` subclass automatically |
| `"not authenticated"` in agent logs | Noise cancellation plugin auth warning | Harmless, does not affect call |
| `"connection refused"` in livekit-sip | Wrong LiveKit URL in `sip.yaml` | Use `localhost:7880` if `network_mode: host`, else Docker service name |

---

*Generated from source: `agent.py`, `assistant.py`, `pipeline.py`, `langgraph_agent.py`, `sip_manager.py`, `sip_api.py`, `webhook_api.py`, `frontend/app/api/connection-details/route.ts`, `frontend/app/api/sip/route.ts`*
