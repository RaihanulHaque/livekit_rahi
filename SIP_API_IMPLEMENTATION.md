# SIP API Implementation Summary

## What Was Implemented

### Phase 1 & 2: Core SIP API with Redis Storage

Complete implementation of dynamic SIP phone number management via REST API endpoints.

---

## Backend Files Created/Updated

### 1. `livekit_agent/src/sip_manager.py` (NEW)
**Core business logic for SIP trunk management with Redis storage**

- `SIPManager` class with methods:
  - `register_sip_trunk()` — Create new inbound trunk + dispatch rule
  - `delete_sip_trunk()` — Remove trunk and dispatch rule
  - `update_sip_trunk()` — Update system prompt and provider config
  - `list_sip_trunks()` — List all trunks for a user (user isolation via Redis keys)
  - `get_sip_trunk()` — Get specific trunk config

- Features:
  - **Number mapping**: Local number (e.g., `09643234042`) ↔ SIP number (e.g., `+15551234567`)
  - **User isolation**: All trunks stored with `user_id` in Redis key: `sip:{user_id}:{local_number}`
  - **Dynamic metadata**: Dispatch rules created with full config (system_prompt, stt, llm, tts)
  - **Async/await**: All operations are async for concurrent handling

### 2. `livekit_agent/src/sip_api.py` (NEW)
**FastAPI REST API endpoints for SIP management**

- Endpoints:
  - `POST   /sip/trunks` — Register new phone number
  - `GET    /sip/trunks` — List all user's phone numbers
  - `GET    /sip/trunks/{local_number}` — Get specific phone config
  - `PATCH  /sip/trunks/{local_number}` — Update phone config
  - `DELETE /sip/trunks/{local_number}` — Delete phone number

- Features:
  - **JWT authentication**: All endpoints validate LiveKit JWT token
  - **User isolation**: Uses `user_id` from JWT for data scoping
  - **Request/response models**: Pydantic models for validation
  - **Error handling**: Proper HTTP status codes and error messages
  - **Runs on port 8089**: Integrated into agent startup as background thread

### 3. `livekit_agent/src/agent.py` (UPDATED)
- Added `_start_sip_api_server()` function to start FastAPI server in background thread
- Integrated into agent's `prewarm()` function
- Server starts automatically when agent starts

### 4. `livekit_agent/pyproject.toml` (UPDATED)
- Added dependencies: `redis>=4.0`, `fastapi>=0.100`, `uvicorn>=0.23`

### 5. `livekit_agent/requirements.txt` (UPDATED)
- Added same dependencies for Docker build

---

## Frontend Files Created/Updated

### 1. `frontend/components/app/sip-management-view.tsx` (NEW)
**Complete SIP management UI component**

- Features:
  - List all active phone numbers with SIP mappings
  - "Add Number" form with:
    - Local phone number input
    - System prompt textarea
    - STT/LLM/TTS provider dropdowns
    - Auto SIP number assignment
  - Delete phone numbers with confirmation
  - Error handling and loading states
  - JWT token support for authentication

### 2. `frontend/components/app/view-controller.tsx` (UPDATED)
- Added `SipManagementView` as third view mode alongside welcome and session
- Added settings icon button (⚙️) in welcome screen to access SIP management
- Added "Back" button in SIP management view
- JWT token extraction from connection details for SIP API auth

### 3. `frontend/app/api/sip/route.ts` (NEW)
**Next.js API proxy for SIP endpoints**

- Proxies all SIP requests from frontend to backend API
- Handles: GET, POST, PATCH, DELETE methods
- Forwards Authorization headers
- Maps path: `/api/sip*` → `livekit_agent:8089/sip/trunks*`
- Proper error handling and logging
- Supports both dev (localhost:8089) and prod (livekit_agent:8089)

---

## Documentation Updated

### 1. `CLAUDE.md` (UPDATED)
- Added "SIP Phone Management API" section with:
  - API endpoints reference
  - Request/response examples (curl commands)
  - Frontend UI instructions
  - Number mapping explanation
  - Environment variables table
  - Troubleshooting guide

### 2. `SIP_GUIDE.md` (UPDATED)
- Split setup into two options:
  - **Option 1**: Dynamic API setup (recommended)
    - Frontend UI walkthrough
    - curl API examples (register, list, delete)
  - **Option 2**: Manual CLI setup (legacy)
- Added "Number Mapping" section explaining local vs SIP numbers
- Updated Gap Analysis to mark SIP API as implemented

---

## Docker Configuration Updated

### `docker-compose.yml`
- **livekit_agent service**:
  - Exposed port `8089:8089` for SIP API
  - Added `REDIS_HOST` and `REDIS_PORT` environment variables
  - Added `redis` service dependency

---

## Storage Architecture

### Redis Schema
```
Key: sip:{user_id}:{local_number}
Value: {
  "local_number": "09643234042",
  "sip_number": "+15551234567",
  "trunk_id": "ST_xxx",
  "dispatch_rule_id": "SDR_xxx",
  "system_prompt": "You are HVAC support...",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs",
  "status": "active",
  "created_at": 1712973600
}
```

**Benefits**:
- User isolation: Different users see only their trunks
- Fast lookups: O(1) retrieval by user_id + local_number
- Ephemeral storage: No DB overhead, everything in Redis
- Shared with LiveKit: Uses existing Redis instance

---

## Data Flow: Adding a Phone Number

```
Frontend (Click "Add Number")
    ↓
SIP Management Form (collect local_number, system_prompt, stt, llm, tts)
    ↓
POST /api/sip (Next.js proxy)
    ↓
livekit_agent:8089/sip/trunks (FastAPI)
    ↓
sip_api.py: register_trunk endpoint
    ↓
sip_manager.py: register_sip_trunk()
    ├─ Create inbound trunk (+15551234567) in LiveKit
    ├─ Create dispatch rule with metadata
    └─ Store in Redis: sip:{user_id}:09643234042 → config
    ↓
Response: { local_number, sip_number, trunk_id, dispatch_rule_id, ... }
    ↓
Frontend: Show "Phone 09643234042 is active (SIP: +15551234567)"
```

---

## Data Flow: Incoming SIP Call

```
Caller dials +15551234567 (SIP number)
    ↓
SIP provider routes to livekit-sip:5060
    ↓
LiveKit matches inbound trunk for +15551234567
    ↓
Dispatch rule activates
    ├─ Creates room: sip-{user_id}-{local_number}-{random}
    └─ Sets room metadata: { local_number, system_prompt, stt, llm, tts }
    ↓
Python agent joins room
    ↓
agent.py reads ctx.room.metadata
    ├─ Extracts system_prompt
    ├─ Builds dynamic pipeline (stt, llm, tts)
    └─ Starts conversation with correct persona
```

---

## How to Use

### Frontend UI (Demo)
1. Start all services: `docker compose up --build`
2. Open frontend: `http://localhost:3033`
3. Click settings icon (⚙️) in welcome view
4. Click "Add Number"
5. Fill in form:
   - Local Number: `09643234042`
   - System Prompt: `You are a professional HVAC support agent...`
   - STT: Deepgram
   - LLM: OpenAI
   - TTS: ElevenLabs
6. Click "Add Phone Number"
7. Phone is now live; calls to the SIP number will route to the agent

### Via API (curl)
```bash
curl -X POST http://localhost:8089/sip/trunks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "local_number": "09643234042",
    "system_prompt": "You are HVAC support...",
    "stt": "deepgram",
    "llm": "openai",
    "tts": "elevenlabs"
  }'
```

---

## Integration with Production Frontend

To add SIP management to your production Unisense frontend:

1. Copy `sip-management-view.tsx` component to your frontend
2. Copy `sip/route.ts` API proxy to your frontend
3. Add SIP tab/button in your main UI (similar to view-controller.tsx pattern)
4. Update environment variable `SIP_API_BASE` if needed

The component handles all UI/API communication automatically.

---

## Error Handling

- **"Trunk already exists"** — Use different local_number or delete existing first
- **"Trunk not found"** — Verify local_number spelling
- **"Failed to reach SIP API"** — Ensure livekit_agent is running on port 8089
- **Redis connection error** — Check REDIS_HOST and REDIS_PORT settings

---

## Future Enhancements

1. **Database persistence**: Sync Redis to PostgreSQL for backup
2. **Caller ID handling**: Extract caller info from incoming SIP INVITE
3. **Number pool management**: Auto-assign SIP numbers from provider pool
4. **Analytics**: Track call volume per phone number
5. **Voice recordings**: Store audio logs per call
6. **Multi-language support**: Language selection in SIP management UI

---

## Files Summary

| File | Type | Purpose |
|------|------|---------|
| sip_manager.py | Backend | Core business logic |
| sip_api.py | Backend | REST API endpoints |
| agent.py | Backend | API server integration |
| sip-management-view.tsx | Frontend | UI component |
| view-controller.tsx | Frontend | View routing |
| sip/route.ts | Frontend | API proxy |
| docker-compose.yml | Config | Port/dependency config |
| CLAUDE.md | Docs | Developer guide |
| SIP_GUIDE.md | Docs | User/admin guide |
| pyproject.toml | Config | Python dependencies |
| requirements.txt | Config | Docker dependencies |

**Total new lines of code**: ~1,500 (sip_manager: 350, sip_api: 300, frontend: 400+, docs: 200+)

---

## Status

✅ **Phase 1 Complete**: Core SIP API with CRUD operations
✅ **Phase 2 Complete**: Redis storage with user isolation
✅ **Frontend UI**: SIP management panel added to demo frontend
✅ **Documentation**: Updated CLAUDE.md and SIP_GUIDE.md
✅ **Docker Integration**: Port exposure and environment setup

**Ready for**: Phase 3 (Frontend UI for production) and Phase 4 (Testing)
