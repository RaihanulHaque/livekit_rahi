# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Cloud Voice AI** — a real-time voice AI assistant built on LiveKit. Users select STT/LLM/TTS providers at runtime via a web UI; the backend Python agent dynamically constructs the pipeline and handles the voice session.

## Commands

### Full Stack (Recommended)
```bash
docker compose up --build        # Start all services
docker compose up livekit_agent  # Start individual service
```
Frontend: http://localhost:3033 | LiveKit: ws://localhost:7880

### Frontend
```bash
cd frontend
pnpm install
pnpm dev          # Dev server (port 3000)
pnpm build        # Production build
pnpm lint         # ESLint
pnpm format       # Prettier
pnpm format:check # Check formatting
```

### Python Agent
```bash
cd livekit_agent
uv sync                            # Install dependencies
python src/agent.py dev            # Development mode
python src/agent.py start          # Production mode
python src/agent.py console        # CLI testing (no browser needed)
python src/agent.py download-files # Pre-download VAD/turn-detector models
ruff format src/                   # Format
ruff check src/                    # Lint
```

## Architecture

### Services (docker-compose.yml)
| Service | Port | Purpose |
|---------|------|---------|
| `livekit` | 7880/7881 | WebRTC server (depends on redis) |
| `redis` | 6379 | LiveKit state store |
| `livekit-sip` | 5060 | Telephony gateway (optional) |
| `livekit_agent` | — | Python agent runtime |
| `frontend` | 3033 | Next.js web UI |

### Dynamic Model Selection + System Prompt Flow

This is the core architectural pattern:

1. User picks STT/LLM/TTS in `frontend/components/app/welcome-view.tsx`
2. User optionally selects an agent profile or writes a custom system prompt in the same view
3. `frontend/components/app/app.tsx` POSTs selections + `system_prompt` to `/api/connection-details`
4. `frontend/app/api/connection-details/route.ts` embeds all of them as JSON in the LiveKit JWT `roomConfig.metadata`
5. `livekit_agent/src/agent.py` reads `ctx.room.metadata` on session start, extracts `system_prompt`
6. `livekit_agent/src/pipeline.py` builds the pipeline via `build_stt_dynamic()`, `build_llm_dynamic()`, `build_tts_dynamic()`
7. `Assistant(instructions=system_prompt)` is instantiated with the per-session prompt
8. **All session state is stateless** — it lives in the JWT, not a database

### System Prompt / Agent Context API

`GET /api/system-prompt?agentId=<id>` — returns `{ agentId, name, systemPrompt }`.

Demo profiles live in `frontend/app/api/system-prompt/route.ts`. In production, replace the `AGENT_PROFILES` map with a real DB query (e.g. `SELECT system_prompt FROM agents WHERE id = $1`).

Available demo profiles: `hvac`, `sales`, `support`.

### Backend Key Files
- `livekit_agent/src/agent.py` — entrypoint; loads VAD, reads room metadata, extracts `system_prompt` from config
- `livekit_agent/src/assistant.py` — `Agent` subclass; accepts optional `instructions` param (falls back to `DEFAULT_INSTRUCTIONS`)
- `livekit_agent/src/pipeline.py` — provider builder functions; add new STT/LLM/TTS providers here
- `livekit_agent/src/langgraph_agent.py` — LangGraph agent with tools (calculator, weather, Tavily search)
- `livekit_agent/src/system_prompt.py` — legacy static HVAC system prompt (kept as reference; runtime uses JWT-injected prompt)
- `livekit_agent/src/sip_manager.py` — SIP trunk management with Redis storage and number mapping
- `livekit_agent/src/sip_api.py` — FastAPI endpoints for SIP trunk CRUD operations (runs on port 8089)
- `livekit_agent/src/setup_sip.py` — CLI script for one-time SIP setup (deprecated; use API instead)

### Frontend Key Files
- `frontend/app/api/connection-details/route.ts` — JWT generation with embedded metadata
- `frontend/components/app/app.tsx` — top-level state for model selections; triggers token refresh on change
- `frontend/components/app/welcome-view.tsx` — model selection dropdowns (STT/LLM/TTS)
- `frontend/app-config.ts` — app title, branding, feature flags (chat input, video, screen share)

### Provider Options
| Type | Options |
|------|---------|
| STT | Deepgram (`flux-general-en`), Whisper (OpenAI) |
| LLM | LangChain/LangGraph (default), OpenAI, Groq, Gemini |
| TTS | ElevenLabs (default), OpenAI, Kokoro (local container) |

## Environment Variables

Copy `.env.example` to `.env`. Required keys:
```
LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
DEEPGRAM_API_KEY
OPENAI_API_KEY
ELEVENLABS_API_KEY
GROQ_API_KEY
GEMINI_API_KEY
NEXT_PUBLIC_LIVEKIT_URL  # Browser-accessible URL (localhost for local dev)
```

Optional overrides: `DEEPGRAM_MODEL`, `LLM_MODEL`, `TTS_VOICE_ID`, `TTS_MODEL`, `TAVILY_API_KEY`

## Adding a New Provider

To add a new STT/LLM/TTS option:
1. Add a case to the relevant builder in `livekit_agent/src/pipeline.py`
2. Add the option to the `<Select>` in `frontend/components/app/welcome-view.tsx`
3. No database changes needed — selections flow through JWT metadata

See `MODEL_SELECTION.md` for a detailed walkthrough of this flow.

## SIP Phone Management API

### Overview

The SIP API enables dynamic provisioning and management of phone numbers for incoming SIP calls. Each phone number maps to a local number (user-facing) and a SIP number (backend), with per-phone configuration for system prompt and STT/LLM/TTS providers.

### Storage

Trunk mappings are stored in Redis with user isolation:
```
Key: sip:{user_id}:{local_number}
Value: {
  sip_number, trunk_id, dispatch_rule_id,
  system_prompt, stt, llm, tts, status, created_at
}
```

### API Endpoints

All endpoints require LiveKit JWT authorization (`Authorization: Bearer <token>`).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/sip` | Register new phone number |
| `GET` | `/api/sip` | List all phone numbers for user |
| `GET` | `/api/sip/{local_number}` | Get specific phone number config |
| `PATCH` | `/api/sip/{local_number}` | Update system prompt / providers |
| `DELETE` | `/api/sip/{local_number}` | Delete phone number |

### Request/Response Examples

**Register a phone number:**
```bash
POST /api/sip
{
  "local_number": "09643234042",
  "system_prompt": "You are HVAC support...",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs",
  "sip_number": "+15551234567"  # optional, auto-assigned if omitted
}

Response (201):
{
  "local_number": "09643234042",
  "sip_number": "+15551234567",
  "trunk_id": "ST_xxx",
  "dispatch_rule_id": "SDR_xxx",
  "system_prompt": "...",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

**List phone numbers:**
```bash
GET /api/sip

Response (200):
[
  {
    "local_number": "09643234042",
    "sip_number": "+15551234567",
    "trunk_id": "ST_xxx",
    "status": "active",
    "created_at": 1712973600
  }
]
```

**Update phone number config:**
```bash
PATCH /api/sip/09643234042
{
  "system_prompt": "New prompt...",
  "stt": "whisper"
}

Response (200): Full updated trunk config
```

**Delete phone number:**
```bash
DELETE /api/sip/09643234042

Response (200):
{
  "deleted": true,
  "local_number": "09643234042",
  "sip_number": "+15551234567",
  "trunk_id": "ST_xxx"
}
```

### Frontend UI

The frontend includes a SIP Management panel accessible via the settings icon in the welcome view. Users can:
- Add new phone numbers with custom prompts and provider configs
- View all active phone numbers and their SIP mappings
- Delete phone numbers

Access the SIP panel: Click the **settings icon** (⚙️) in the top-right corner of the welcome screen.

### Number Mapping (BTRC Compliance)

To support local phone number regulations (e.g., Bangladesh BTRC rules):

1. **Local number** (e.g., `09643234042`) — what users see and dial
2. **SIP number** (e.g., `+15551234567`) — actual SIP trunk number from provider

When a call arrives on the SIP number, the dispatch rule's room metadata contains the `local_number`, so the agent knows which customer it is.

### Adding to Production

In your production frontend, integrate the SIP management UI from `frontend/components/app/sip-management-view.tsx`. The component handles all CRUD operations via the `/api/sip` proxy route.

### Environment Variables

| Var | Default | Purpose |
|-----|---------|---------|
| `SIP_API_BASE` | `http://localhost:8089` | Backend SIP API URL |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |

### Troubleshooting

**"Failed to reach SIP API"** — Ensure `livekit_agent` service is running and port 8089 is accessible.

**"Trunk already exists"** — Phone number already provisioned. Delete it first or use a different number.

**Redis connection error** — Verify Redis is running and accessible at `REDIS_HOST:REDIS_PORT`.
