# Cloud Voice AI (Simplified)

This stack is now intentionally organized into two app concerns:

- frontend: Next.js web client
- backend: LiveKit + Python agent runtime

The runtime path is a single Docker Compose file with no separate inference containers.

## Architecture

- livekit: real-time room server
- livekit_agent: STT + LLM + TTS orchestration
- frontend: browser UI

STT, LLM, and TTS run through cloud providers (Deepgram, OpenAI-compatible endpoint, ElevenLabs), so no local kokoro/llama/whisper services are required.

---

## Full System Flow (Architect View)

This section walks through every step from the moment a user opens the browser to the moment the voice session ends. Two modes are supported — **Custom Prompt** (inline) and **Agent ID** (SaaS fetch). Both share the same core path; they only differ in how the system prompt is resolved.

---

### Phase 1 — User opens the browser

```
Browser
  └── GET http://localhost:3033
        └── Next.js frontend serves the React app
              └── WelcomeView renders:
                    - STT / LLM / TTS dropdowns
                    - Mode toggle: [Custom Prompt] [Agent ID]
```

Nothing connects to LiveKit yet. The user configures their session before starting.

---

### Phase 2 — User clicks "Start Call"

The frontend POSTs to its own internal API route to get a LiveKit access token.

```
Browser
  └── POST /api/connection-details
        body: {
          stt: "deepgram",
          llm: "langchain",
          tts: "elevenlabs",

          // Custom Prompt mode:
          system_prompt: "You are an HVAC support agent..."

          // — OR — Agent ID mode:
          agent_id: "2008011"
          // (system_prompt is null, agent fetches it later)
        }
```

Inside `connection-details/route.ts` (Next.js server-side, never exposed to the browser):

```
connection-details/route.ts
  ├── Reads LIVEKIT_API_KEY + LIVEKIT_API_SECRET from server env
  ├── Generates a unique room name  (voice_assistant_room_XXXX)
  ├── Packs everything into roomMetadata JSON:
  │     { stt, llm, tts, system_prompt, agent_id }
  ├── Signs a LiveKit JWT:
  │     - identity: voice_assistant_user_XXXX
  │     - ttl: 15 minutes
  │     - roomConfig.metadata: <roomMetadata JSON string>
  └── Returns to browser: { serverUrl, roomName, participantToken }
```

The system prompt (if Custom Prompt mode) lives inside the JWT at this point. In Agent ID mode the JWT only carries the agent_id — a short string — so the JWT stays small regardless of how large the real prompt is.

---

### Phase 3 — Browser connects to LiveKit

```
Browser (livekit-client SDK)
  └── WebSocket connect → LiveKit Server (ws://localhost:7880)
        JWT verified by LiveKit using LIVEKIT_API_SECRET
        Room created with metadata attached
        Browser joins as participant
```

LiveKit sees a new room and dispatches a job to an available agent worker.

---

### Phase 4 — LiveKit dispatches to the agent

```
LiveKit Server
  └── Assigns job to livekit_agent container
        └── agent.py: my_agent(ctx) called
              ├── ctx.connect()  — agent joins the room
              ├── config = json.loads(ctx.room.metadata)
              │     → { stt, llm, tts, system_prompt/agent_id }
              │
              ├── [Custom Prompt mode]
              │     system_prompt = config["system_prompt"]
              │     used directly — no external call needed
              │
              └── [Agent ID mode]
                    agent_id = config["agent_id"]
                    ↓  (see Phase 5)
```

---

### Phase 5 — Agent fetches system prompt from SaaS backend (Agent ID mode only)

This is the key step that keeps large prompts out of the JWT and allows centralized management.

```
livekit_agent (inside Docker, session start)
  │
  ├── Signs a short-lived JWT (30s TTL):
  │     payload: { iss: LIVEKIT_API_KEY, exp: now + 30 }
  │     signed with: LIVEKIT_API_SECRET  (HS256)
  │
  └── GET {SAAS_BACKEND_URL}/api/v1/agents/2008011
        Authorization: Bearer <signed-jwt>
              │
              ▼
        SaaS Backend (your server / test-back.py)
          ├── Extracts Bearer token from header
          ├── Verifies HMAC-SHA256 signature using LIVEKIT_API_SECRET
          ├── Checks iss == LIVEKIT_API_KEY
          ├── Checks token not expired
          └── Returns: { agent_id, name, system_prompt }
              │
              ▼
        agent.py receives system_prompt
        → no new secrets needed, reuses the LiveKit key pair
```

Why this is safe: the SaaS backend already holds `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` (you configured them). Verification is pure cryptography — no database lookup, no network round-trip to LiveKit.

---

### Phase 6 — Voice session runs

```
agent.py
  └── build_session(vad, config)
        ├── STT: Deepgram / ElevenLabs / Whisper
        ├── LLM: LangChain / OpenAI / Groq / Gemini
        └── TTS: ElevenLabs / OpenAI / Kokoro
              │
              ▼
        session.start(
          agent=Assistant(instructions=system_prompt),
          room=ctx.room
        )

Real-time audio loop:
  User speaks
    → VAD detects speech end
    → STT transcribes to text
    → LLM generates response
    → TTS synthesizes audio
    → Audio streamed back to browser via LiveKit WebRTC
  (repeat)
```

Each turn is also appended to an in-memory transcript list for the call record.

---

### Phase 7 — Call ends

```
User disconnects (closes tab / clicks end)
  └── session "close" event fires in agent.py
        ├── [Redis available]
        │     Transcript saved to Redis under key: call:{agent_id}:{room_name}
        │     TTL: 30 days
        │
        └── [CALLBACK_WEBHOOK_URL set]
              POST {CALLBACK_WEBHOOK_URL}/api/v1/call-completed
              body: {
                agent_id, room_name,
                local_number, sip_number,
                duration_seconds, status: "completed",
                transcript: [{ role, content, total_tokens }]
              }
```

---

### Full flow diagram (condensed)

```
Browser
  │  POST /api/connection-details  { stt, llm, tts, agent_id }
  ▼
Next.js API Route
  │  Signs LiveKit JWT with roomMetadata  { stt, llm, tts, agent_id }
  ▼
LiveKit Server  ←──────────────── Browser connects via WebSocket (JWT)
  │  Dispatches job to agent pool
  ▼
livekit_agent (Python)
  │  Reads room metadata
  │  Signs 30s JWT → GET /api/v1/agents/2008011
  ▼
SaaS Backend
  │  Verifies JWT → returns system_prompt
  ▼
livekit_agent
  │  Builds STT + LLM + TTS pipeline
  │  Starts voice session
  ▼
Real-time audio  ◄──────────────► Browser (WebRTC via LiveKit)
  │
  └── On close → Redis + Webhook callback → SaaS Backend
```

---

### Where each service lives

| Service | Dev | Production |
|---|---|---|
| Browser | localhost:3033 | your domain |
| Next.js frontend | Docker (port 3033) | Vercel / any Node host |
| LiveKit server | Docker (port 7880) | LiveKit Cloud or self-hosted VM |
| livekit_agent | Docker | Auto-scaled container pool |
| SaaS backend | test-back.py (port 8083) | Your API server |
| Redis | omitted in dev | Docker / managed Redis |

In production, the agent containers and LiveKit server can be on completely separate machines. They only need three things in common: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`.

## Quick Start

1. Copy env template:

```bash
cp .env.example .env
```

2. Fill required keys in .env:

- DEEPGRAM_API_KEY
- OPENAI_API_KEY
- ELEVENLABS_API_KEY

3. Start everything:

```bash
docker compose up --build
```

4. Open http://localhost:3033

---

## Local Development (fast builds)

A separate dev compose file skips heavy production dependencies (CUDA torch, noise-cancellation, SIP, Redis) and runs only the three services you need: `livekit`, `livekit_agent`, and `frontend`.

```bash
docker compose -f docker-compose.dev.yml up --build
```

To test the Agent ID flow locally, run the backend simulator alongside:

```bash
python test-back.py   # starts on http://0.0.0.0:8083
```

---

## Agent ID Flow (SaaS-ready)

Instead of embedding a full system prompt in the LiveKit JWT (which has size limits and exposes prompt content in the token), you can pass only an `agent_id`. The agent fetches the system prompt from your SaaS backend at session start — the JWT stays tiny.

**Frontend:** toggle to "Agent ID" mode in the welcome screen, enter the agent ID.

**Agent:** on session start, makes an authenticated HTTP request:
```
GET {SAAS_BACKEND_URL}/api/v1/agents/{agent_id}
Authorization: Bearer <livekit-signed-jwt>
```

**Auth mechanism:** The agent signs a short-lived JWT (30s TTL) using `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. The SaaS backend verifies the signature with the same pair — no extra secrets needed.

Set the backend URL in your env:
```bash
SAAS_BACKEND_URL=https://your-saas.com          # production
SAAS_BACKEND_URL=http://host.docker.internal:8083  # local testing with test-back.py
```

---

## Backend Modularity

The backend entrypoint is thin by design:

- livekit_agent/src/agent.py: runtime wiring, session start, agent_id → system prompt fetch
- livekit_agent/src/assistant.py: assistant behavior and prompt attachment
- livekit_agent/src/pipeline.py: STT/LLM/TTS provider builders
- livekit_agent/src/system_prompt.py: legacy static prompt (reference only)

This split keeps provider swapping and future tool/plugin additions localized to pipeline and config layers.

---

## Environment Variables

### Core

| Variable | Description |
|---|---|
| `LIVEKIT_URL` | WebSocket URL of the LiveKit server |
| `LIVEKIT_API_KEY` | LiveKit API key (see security note below) |
| `LIVEKIT_API_SECRET` | LiveKit API secret — **keep this private** |
| `DEEPGRAM_API_KEY` | Deepgram STT key |
| `OPENAI_API_KEY` | OpenAI key |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS key |

### Optional overrides

| Variable | Description |
|---|---|
| `DEEPGRAM_MODEL` | Deepgram model name |
| `DEEPGRAM_EAGER_EOT_THRESHOLD` | End-of-turn sensitivity |
| `LLM_MODEL` | LLM model name |
| `TTS_MODEL` | TTS model name |
| `TTS_VOICE_ID` | ElevenLabs voice ID |
| `SAAS_BACKEND_URL` | URL of your SaaS backend for agent_id fetch |
| `CALLBACK_WEBHOOK_URL` | URL notified on call completion |

---

## Security: API Key vs API Secret

This is easy to confuse and important to get right.

**`LIVEKIT_API_KEY`** is like a username. It appears as the `iss` (issuer) claim inside every JWT. Since JWTs are base64-encoded (not encrypted), it is effectively public. Knowing it does not help an attacker forge tokens.

**`LIVEKIT_API_SECRET`** is the actual signing key. It is used to create the HMAC-SHA256 signature that makes JWTs unforgeable. Anyone who knows this secret can sign arbitrary tokens and impersonate your agent or your users.

In dev mode (`--dev` flag), LiveKit defaults to `devkey` / `secret`. These are fine on localhost. **Never use them in production.**

### Generating production credentials

```bash
# API secret — must be long and random (256-bit recommended)
openssl rand -hex 32
# → e.g. a3f8c2e1b4d7f09e2a5c8b1e4d7a0f3c6b9e2d5a8c1f4b7e0d3c6a9f2e5b8

# API key — just a consistent identifier, can be shorter
openssl rand -hex 16
# → e.g. 4a7f2c1b8e3d9f5a
```

In `.env`:
```bash
LIVEKIT_API_KEY=4a7f2c1b8e3d9f5a          # can be anything, just consistent
LIVEKIT_API_SECRET=a3f8c2e1b4d7f09e...    # this is what must be kept secret
```

In your LiveKit server config (self-hosted, non-dev mode):
```yaml
keys:
  4a7f2c1b8e3d9f5a: a3f8c2e1b4d7f09e...
```

---

## Project Structure

```
.
├── frontend/
├── livekit_agent/
│   ├── src/
│   │   ├── agent.py
│   │   ├── assistant.py
│   │   ├── pipeline.py
│   │   └── ...
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   ├── requirements.txt
│   └── requirements.dev.txt
├── test-back.py          ← local SaaS backend simulator (port 8083)
├── docker-compose.yml    ← production (GPU, SIP, Redis)
├── docker-compose.dev.yml ← local dev (fast builds, 3 services)
├── .env.example
└── README.md
```

---

## Notes For Production

- Replace `--dev` mode with a proper LiveKit config and strong `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET`.
- Replace `test-back.py` with your real SaaS backend. The `/api/v1/agents/{id}` endpoint and the `verify_livekit_token` dependency are the only pieces that need to carry over.
- Add observability (metrics, traces, structured logs).
- Put secrets in a manager (not plain `.env` in CI/CD).
- Add CI checks for formatting, tests, and image builds.
