# SIP & Telephony Guide — Cloud Voice AI

This document covers how SIP telephony works in this codebase, how it integrates with the existing web-based voice pipeline, and answers common questions about scaling to multi-tenant production use.

---

## Table of Contents

1. [Current Architecture at a Glance](#current-architecture-at-a-glance)
2. [How Web Calls Work (Existing)](#how-web-calls-work-existing)
3. [How SIP Calls Work (Telephony)](#how-sip-calls-work-telephony)
4. [SIP Setup Steps](#sip-setup-steps)
5. [Multi-Tenant SIP Architecture](#multi-tenant-sip-architecture)
6. [Gap Analysis: What the Prototype Handles vs What Production Needs](#gap-analysis)
7. [Q&A](#qa)

---

## Current Architecture at a Glance

```
Services (docker-compose.yml):
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   frontend   │  │   livekit    │  │    redis     │
│  (Next.js)   │  │  (WebRTC)    │  │  (state)     │
│  port 3033   │  │  port 7880   │  │  port 6379   │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       │          ┌──────┴───────┐  ┌──────────────┐
       └──────────│ livekit_agent│  │  livekit-sip │
                  │  (Python)    │  │  port 5060   │
                  └──────────────┘  └──────────────┘
```

**Key files:**

| File | Purpose |
|------|---------|
| `livekit_agent/src/agent.py` | Session entrypoint; reads room metadata, builds pipeline |
| `livekit_agent/src/assistant.py` | Agent class; accepts `instructions` (system prompt) |
| `livekit_agent/src/pipeline.py` | Dynamic STT/LLM/TTS builder functions |
| `livekit_agent/src/langgraph_agent.py` | LangGraph agent with tools (calculator, weather, Tavily) |
| `livekit_agent/src/setup_sip.py` | One-time script to register SIP trunk + dispatch rule |
| `frontend/app/api/connection-details/route.ts` | JWT generation with embedded metadata |
| `frontend/app/api/system-prompt/route.ts` | Demo agent profile lookup (hvac, sales, support) |
| `sip.yaml` | SIP server configuration |
| `docker-compose.yml` | Service orchestration |

---

## How Web Calls Work (Existing)

This is the flow that already works:

```
1. User opens frontend (localhost:3033)
2. Selects STT / LLM / TTS providers from dropdowns
3. Optionally selects agent profile (hvac, sales, support) or writes custom prompt
4. Clicks "Start Call"
        │
        ▼
5. Frontend POSTs to /api/connection-details:
   { stt: "deepgram", llm: "langchain", tts: "elevenlabs", system_prompt: "You are..." }
        │
        ▼
6. route.ts embeds all config as JSON in LiveKit JWT roomConfig.metadata
   Returns: { serverUrl, roomName, participantToken }
        │
        ▼
7. Browser connects to LiveKit room using token
        │
        ▼
8. Python agent receives session:
   - Reads ctx.room.metadata → extracts stt, llm, tts, system_prompt
   - Calls build_session(config) → creates dynamic STT/LLM/TTS pipeline
   - Starts Assistant(instructions=system_prompt)
   - Conversation begins
```

**Key design choice:** Everything is stateless. Config lives in the JWT, not a database. Each session is self-contained.

---

## How SIP Calls Work (Telephony)

SIP calls follow a different path because the caller is on a phone — they can't select providers or type a system prompt.

```
1. Someone dials your SIP phone number (+12707768622)
        │
        ▼
2. SIP provider routes call to your server (89.116.34.144:5060)
        │
        ▼
3. livekit-sip container receives SIP INVITE
        │
        ▼
4. LiveKit checks: is there an INBOUND TRUNK matching this phone number?
   - YES → proceed
   - NO  → reject with 486 "flood" (this is what was happening)
        │
        ▼
5. LiveKit checks: is there a DISPATCH RULE for this trunk?
   - YES → create room + SIP participant
   - NO  → reject
        │
        ▼
6. Dispatch rule creates room "sip-call-{random}" and dispatches agent
        │
        ▼
7. Python agent joins the room:
   - ctx.room.metadata is minimal (just "sip-inbound" from dispatch rule)
   - No STT/LLM/TTS selection — uses defaults
   - No custom system_prompt — uses DEFAULT_INSTRUCTIONS
   - Conversation starts with default persona
```

### The Two Things SIP Needs That Web Doesn't

| Concept | What it does | Web equivalent |
|---------|-------------|----------------|
| **Inbound Trunk** | Tells LiveKit "accept calls to this phone number" | Not needed (browser connects directly) |
| **Dispatch Rule** | Tells LiveKit "put this caller in a room and start an agent" | Frontend + /api/connection-details does this |

---

## SIP Setup Steps

### Prerequisites

- Docker services running (`docker compose up`)
- SIP provider configured to route calls to your server IP (`89.116.34.144:5060`)
- Phone number purchased from SIP provider

### Step 1: Run the setup script

```bash
docker compose exec livekit_agent python src/setup_sip.py
```

This creates:
- **Inbound trunk** for `+12707768622` with Krisp noise cancellation
- **Dispatch rule** that routes each caller to an individual room (`sip-call-*`) and auto-dispatches the default agent

### Step 2: Verify

After running the script, test by calling the phone number. The logs should show the call being accepted instead of rejected with 486.

### Configuration reference

**sip.yaml** (mounted into livekit-sip container):
```yaml
api_key: devkey
api_secret: secret
ws_url: ws://livekit:7880
redis:
  address: redis:6379
sip_port: 5060
rtp_port: 10000-10100
use_external_ip: true
```

**docker-compose.yml ports for SIP:**
- `5060:5060/udp` and `5060:5060/tcp` — SIP signaling
- `10000-10100:10000-10100/udp` — RTP media (audio)

---

## Multi-Tenant SIP Architecture

### The model: one phone number per agent

Each **agent** (not company) gets its own phone number. This codebase doesn't know about companies or agents — it just receives a system prompt and builds the voice pipeline. The agent definitions live in your other codebase.

```
Same SIP Server (89.116.34.144:5060)
                 │
   ┌─────────────┼─────────────┐
   │             │             │
+1-555-0001  +1-555-0002  +1-555-0003     ← one phone number per agent
Trunk: HVAC  Trunk: Sales Trunk: Booking  ← one inbound trunk per agent
Rule: →meta  Rule: →meta  Rule: →meta     ← dispatch rule sets room metadata
   │             │             │
 ┌─┴─┐        ┌─┴─┐        ┌─┴─┐
 R1  R2       R3  R4       R5  R6          ← each caller gets own room
 +ag +ag      +ag +ag      +ag +ag         ← same Python agent, different prompt
```

### How it works

1. Each agent's dispatch rule sets **room metadata** with `system_prompt`, `stt`, `llm`, `tts`
2. The room metadata is **identical in shape** to what the web frontend sends via JWT
3. The Python agent reads `ctx.room.metadata` and builds the pipeline — same code path for web and SIP
4. LiveKit doesn't know about agents or companies — it just routes phone numbers to rooms with metadata

### What you need for each agent

1. **Phone number** — purchased from your SIP provider
2. **Inbound trunk** — maps that number to LiveKit (created by `setup_sip.py`)
3. **Dispatch rule** — creates rooms with the agent's metadata (created by `setup_sip.py`)

### How the Python agent handles SIP calls

The dispatch rule's `roomConfig.metadata` contains the same JSON shape as web calls:

```json
{
  "system_prompt": "You are a professional HVAC support agent...",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs"
}
```

The agent reads this from `ctx.room.metadata` — no special SIP handling needed. Web and SIP calls go through the exact same code in `agent.py`.

### For production (pointer metadata)

Instead of embedding the full system prompt in the dispatch rule, use a pointer:

```json
{
  "agent_id": "agt_123",
  "stt": "deepgram",
  "llm": "openai",
  "tts": "elevenlabs"
}
```

Then have the Python agent fetch the full prompt from your external API at session start (see `SYSTEM_PROMPT_RUNTIME.md`).

### Scaling: what happens with 100 concurrent callers?

- Each caller gets their own **isolated room** (via `SIPDispatchRuleIndividual`)
- LiveKit handles many concurrent rooms — each room is lightweight
- The Python agent process spawns a new session per room automatically
- No shared state between calls
- For heavy load: run multiple `livekit_agent` containers (horizontal scaling)

---

## Gap Analysis

### What the prototype handles well

| Feature | Status | Notes |
|---------|--------|-------|
| Dynamic STT/LLM/TTS selection (web) | Working | Via JWT metadata |
| Agent profiles with custom system prompts (web) | Working | 3 demo profiles (hvac, sales, support) |
| SIP call reception | Working | After running setup_sip.py |
| Per-call room isolation | Working | SIPDispatchRuleIndividual |
| Noise cancellation for SIP | Working | BVCTelephony for SIP participants, BVC for web |
| Auto-greeting on session start | Working | assistant.py on_enter() |

### What needs work for production multi-tenant SIP

| Gap | Impact | Fix | Status |
|-----|--------|-----|--------|
| SIP calls get DEFAULT_INSTRUCTIONS only | All phone callers get same generic persona | Dispatch rule sets room metadata with system_prompt | **Fixed** (setup_sip.py now sets per-agent metadata) |
| SIP calls use default STT/LLM/TTS | No per-agent provider customization via phone | Dispatch rule metadata includes stt/llm/tts config | **Fixed** (same metadata shape as web calls) |
| Single phone number in setup_sip.py | Only one agent supported | Extended script to support multiple agents via AGENT_PHONE_MAP | **Fixed** |
| LangGraph has hardcoded system prompt | When using `langchain` LLM, LangGraph prepends its own SystemMessage | Refactor `build_graph(system_prompt)` per SYSTEM_PROMPT_RUNTIME.md | Open (only affects `langchain` LLM option) |
| No auth on /api/connection-details | Anyone can create web sessions | Add auth middleware before going to production | Open |
| Full system prompt in JWT (web flow) | Prompt text visible to client, JWT size risk | Switch to pointer metadata (agent_id) + server-side fetch | Open (fine for prototype) |

### Is the prototype good enough to push to production codebase?

**For web-only use: Yes.** The metadata-through-JWT pattern is clean, the dynamic pipeline works, and the agent profile system is functional.

**For SIP/telephony: Partially.** The infrastructure works (SIP server, trunk, dispatch, room creation, agent dispatch), but the agent doesn't yet know *which company* a phone call belongs to. You need either:
- **Option A (simpler):** One dispatch rule per company, each with different metadata containing `tenant_id` and `agent_id`
- **Option B (scalable):** Caller ID lookup in the agent at session start

The LangGraph hardcoded system prompt is the biggest code-level issue — it ignores the injected `instructions` parameter.

---

## Q&A

### General SIP Questions

**Q: Do I need a separate SIP server for each company?**
A: No. One SIP server (one IP) handles all companies. The phone number in the incoming SIP INVITE determines which trunk and dispatch rule to use.

**Q: Do I need a separate phone number for each agent?**
A: Yes. Each agent gets its own phone number, inbound trunk, and dispatch rule. The dispatch rule sets the room metadata with that agent's system prompt and provider config. The SIP server IP stays the same for all.

**Q: What is an "inbound trunk"?**
A: It's a registration that tells LiveKit: "when a call arrives for phone number X, accept it." Without a trunk, calls are rejected (the 486 "flood" error you saw).

**Q: What is a "dispatch rule"?**
A: It tells LiveKit what to do after accepting a call: create a room, name it, and optionally dispatch an agent to join it.

**Q: Can multiple callers use the same phone number at once?**
A: Yes. Each caller gets their own room. The `SIPDispatchRuleIndividual` rule creates a new room per call. 100 people calling the same number = 100 separate rooms, each with their own agent session.

**Q: What was the "486 flood" error in the logs?**
A: LiveKit SIP received the call but couldn't find a matching inbound trunk or dispatch rule, so it rejected it. Running `setup_sip.py` fixes this by creating both.

### Architecture Questions

**Q: Why don't SIP calls go through the JWT metadata flow like web calls?**
A: Because phone callers can't select providers or write system prompts. The call arrives as a raw SIP INVITE with only the phone number. The dispatch rule is what creates the room and sets initial metadata.

**Q: How does the agent know which system prompt to use for a SIP call?**
A: The dispatch rule sets `roomConfig.metadata` with the agent's `system_prompt`, `stt`, `llm`, and `tts`. The Python agent reads `ctx.room.metadata` — the same code path as web calls. The dispatch rule effectively replaces the frontend's role in setting up the session config.

**Q: Why not use named agents (`@server.rtc_session(agent_name="support")`) instead of metadata?**
A: The current codebase uses a single generic agent and passes everything via metadata. This is simpler for prototyping — one agent process handles all profiles. Named agents would require separate handlers and potentially separate containers. The metadata approach works fine; it just needs a resolver for SIP calls.

**Q: Is the single-agent-with-metadata approach okay for production?**
A: Yes. It's actually preferred when all agents share the same code and only differ by system prompt and provider config. Named agents are useful when agent types have fundamentally different code paths (different tools, different LangGraph workflows, etc.).

**Q: What about the LangGraph hardcoded system prompt?**
A: This is a known issue. In `langgraph_agent.py`, the `call_model()` function prepends its own `SystemMessage` regardless of what `Assistant(instructions=...)` sets. For production, refactor to `build_graph(system_prompt_text)` as described in `SYSTEM_PROMPT_RUNTIME.md`.

### Scaling Questions

**Q: How many concurrent SIP calls can this handle?**
A: LiveKit itself handles thousands of rooms. The bottleneck is the Python agent — each call runs STT + LLM + TTS. For high concurrency, run multiple `livekit_agent` containers. LiveKit distributes sessions across available workers.

**Q: Do I need to scale the SIP server separately?**
A: For moderate load (< 100 concurrent calls), one `livekit-sip` container is fine. For higher load, LiveKit Cloud handles SIP scaling automatically. Self-hosted requires manual scaling.

**Q: What happens if the agent crashes mid-call?**
A: The caller hears silence. LiveKit doesn't auto-reconnect agents. For production, add health checks and container restart policies (already configured in docker-compose.yml with `restart: unless-stopped`).

### Setup Questions

**Q: How do I add a new company's phone number?**
A: Run `setup_sip.py` with the new number (modify `SIP_TRUNK_NUMBER`), or extend it to accept parameters. Each company needs its own trunk + dispatch rule.

**Q: Do I need to restart services after creating trunks/rules?**
A: No. Trunks and dispatch rules are stored in Redis and take effect immediately.

**Q: How do I list existing trunks and dispatch rules?**
A: The `setup_sip.py` script prints existing ones before creating new ones. You can also run the list commands inside the container:
```python
# Inside docker compose exec livekit_agent python
from livekit import api
import asyncio

async def list_all():
    lkapi = api.LiveKitAPI()
    trunks = await lkapi.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    rules = await lkapi.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    print("Trunks:", trunks)
    print("Rules:", rules)
    await lkapi.aclose()

asyncio.run(list_all())
```

**Q: Can I delete a trunk or dispatch rule?**
A: Yes, via the LiveKit API:
```python
await lkapi.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id="ST_xxx"))
await lkapi.sip.delete_sip_dispatch_rule(api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id="SDR_xxx"))
```

### Security Questions

**Q: Can anyone call my SIP number and use my AI agent?**
A: Yes, unless you restrict it. Use `allowed_numbers` on the inbound trunk to whitelist specific caller numbers, or use `allowed_addresses` to restrict by IP.

**Q: Is the system prompt visible to callers?**
A: For web: the full prompt is in the JWT metadata, which is client-readable. For production, use pointer metadata (`agent_id`) instead. For SIP: the prompt is server-side only, not exposed to the caller.

**Q: Should I use authentication on the inbound trunk?**
A: If your SIP provider supports it, yes. Add `auth_username` and `auth_password` to the trunk configuration. Not all providers support this (e.g., Twilio Elastic SIP Trunking doesn't).
