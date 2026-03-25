# Dynamic Model Selection Architecture

This document describes how the LiveKit Voice AI agent system supports dynamic model selection at runtime, allowing users to switch between different STT (Speech-to-Text), LLM (Language Model), and TTS (Text-to-Speech) providers without rebuilding the Docker container.

## Overview

The model selection flow works as follows:

```
User selects models in browser UI
    ↓
Frontend sends POST to /api/connection-details with stt, llm, tts choices
    ↓
Next.js API creates JWT token with model config embedded in roomConfig.metadata
    ↓
Frontend connects to LiveKit room with token
    ↓
Agent reads room.metadata at session startup
    ↓
Agent dynamically builds STT/LLM/TTS pipelines based on selection
    ↓
Agent starts session with selected providers
```

## Frontend Components

### 1. Model Selection UI (`frontend/components/app/welcome-view.tsx`)

The welcome screen displays three dropdown selectors:

```tsx
<Select value={stt} onValueChange={setStt}>
  <SelectTrigger className="w-[140px]">
    <SelectValue placeholder="STT Model" />
  </SelectTrigger>
  <SelectContent>
    <SelectItem value="deepgram">Deepgram</SelectItem>
    <SelectItem value="whisper">Whisper</SelectItem>
  </SelectContent>
</Select>
```

**Available Options:**
- **STT**: deepgram, whisper
- **LLM**: langchain, openai, groq
- **TTS**: elevenlabs, kokoro, openai

### 2. State Management (`frontend/components/app/app.tsx`)

React state tracks the three model selections:

```tsx
const [stt, setStt] = useState('deepgram');
const [llm, setLlm] = useState('langchain');
const [tts, setTts] = useState('elevenlabs');
```

These are passed down through the component tree to `ViewController` and `WelcomeView`.

### 3. Custom Token Source

When the user clicks "Start Call", a custom `TokenSource` is created that:

1. Sends a POST request to `/api/connection-details`
2. Includes the selected models in the request body
3. Receives back a JWT participant token with the metadata embedded

```tsx
const tokenSource = useMemo(() => {
  return TokenSource.custom(async () => {
    const res = await fetch('/api/connection-details', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stt,    // e.g., "deepgram"
        llm,    // e.g., "langchain"
        tts,    // e.g., "elevenlabs"
        room_config: appConfig.agentName
          ? { agents: [{ agent_name: appConfig.agentName }] }
          : undefined,
      }),
    });
    return await res.json();
  });
}, [appConfig, stt, llm, tts]);
```

**Important:** The `tokenSource` updates whenever any model selection changes, ensuring fresh tokens if user switches models before connecting.

## Backend API Endpoint

### Route: `frontend/app/api/connection-details/route.ts`

This Next.js API endpoint processes the model selection and creates a JWT token with embedded metadata.

#### Request Body
```json
{
  "stt": "deepgram",
  "llm": "langchain",
  "tts": "elevenlabs",
  "room_config": {
    "agents": [{ "agent_name": "my_agent" }]
  }
}
```

#### Process

1. **Parse request** to extract stt, llm, tts choices
2. **Generate credentials**:
   - Unique room name
   - Unique participant identity
3. **Create metadata JSON**:
   ```json
   {
     "stt": "deepgram",
     "llm": "langchain",
     "tts": "elevenlabs"
   }
   ```
4. **Create AccessToken** (JWT) with metadata embedded in roomConfig:
   ```tsx
   at.roomConfig = new RoomConfiguration({
     agents: agentName ? [{ agentName }] : undefined,
     metadata: roomMetadata,  // ← Contains model selections
   });
   ```
5. **Return connection details**:
   ```json
   {
     "serverUrl": "http://localhost:7880",
     "roomName": "voice_assistant_room_8882",
     "participantToken": "eyJhbGciOiJIUzI1NiJ9...",
     "participantName": "user"
   }
   ```

#### Key Implementation Detail

The metadata is **embedded in the JWT token itself**, not stored on the server. This means:
- ✅ Agent immediately reads user's model choice on session start
- ✅ No database required
- ✅ Stateless backend
- ✅ Scales horizontally

## Agent Side

### Session Initialization (`livekit_agent/src/agent.py`)

When a user connects, the agent:

1. Awaits connection to the room
2. Parses `ctx.room.metadata` (which contains the JWT room config metadata)
3. Passes the config to `build_session`

```python
await ctx.connect()

import json
try:
    config = json.loads(ctx.room.metadata or "{}")
except json.JSONDecodeError:
    config = {}

session = build_session(vad=ctx.proc.userdata["vad"], config=config)
```

### Dynamic Provider Building (`livekit_agent/src/pipeline.py`)

Three builder functions dynamically instantiate providers based on config:

#### `build_stt_dynamic(config)`
```python
provider = config.get("stt", "deepgram")  # Default: deepgram

if provider == "deepgram":
    return deepgram.STTv2(
        model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", "flux-general-en")),
        api_key=keys.get("deepgram", os.getenv("DEEPGRAM_API_KEY")),
    )
elif provider == "whisper":
    return openai.STT(
        model=config.get("stt_model", "whisper-1"),
        api_key=keys.get("openai", os.getenv("OPENAI_API_KEY")),
    )
```

#### `build_llm_dynamic(config)`
```python
provider = config.get("llm", "langchain")  # Default: langchain

if provider == "openai":
    return openai.LLM(...)
elif provider == "groq":
    return groq.LLM(...)
elif provider == "langchain":
    return build_llm_langchain(graph_app)
```

#### `build_tts_dynamic(config)`
```python
provider = config.get("tts", "elevenlabs")  # Default: elevenlabs

if provider == "elevenlabs":
    return elevenlabs.TTS(...)
elif provider == "kokoro":
    return build_tts_kokoro()
elif provider == "openai":
    return openai.TTS(...)
```

### Fallback Strategy

Each builder function falls back gracefully:

1. **Config value** → If provided by user via UI
2. **Environment variable** → If set in `.env` or Docker
3. **Hardcoded default** → The system default

Example for Deepgram model:
```python
model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", "flux-general-en"))
```

This means:
- User can override via frontend UI
- Ops team can set defaults via `.env`
- System always has a fallback

## Environment Variables

To provide defaults when no user selection is made, set these in `.env` or `docker-compose.yml`:

```bash
# STT (Speech-to-Text)
DEEPGRAM_MODEL=flux-general-en
DEEPGRAM_API_KEY=your_key

# LLM (Language Model)
LLM_MODEL=gpt-4o-mini
GROQ_API_KEY=your_key

# TTS (Text-to-Speech)
TTS_MODEL=eleven_flash_v2_5
TTS_VOICE_ID=iP95p4xoKVk53GoZ742B
ELEVEN_API_KEY=your_key
```

## Docker Deployment

The `docker-compose.yml` passes environment variables to both frontend and agent:

```yaml
frontend:
  environment:
    - NEXT_PUBLIC_LIVEKIT_URL=ws://localhost:7880
    - LIVEKIT_URL=ws://livekit:7880
    - LIVEKIT_API_KEY=devkey
    - LIVEKIT_API_SECRET=secret

livekit_agent:
  environment:
    - LIVEKIT_URL=ws://livekit:7880
    - DEEPGRAM_API_KEY=${DEEPGRAM_API_KEY}
    - GROQ_API_KEY=${GROQ_API_KEY}
    - ELEVEN_API_KEY=${ELEVEN_API_KEY}
```

## Adding New Model Providers

To add support for a new STT/LLM/TTS provider:

### 1. Add UI Option

Edit `frontend/components/app/welcome-view.tsx`:

```tsx
<SelectItem value="new_provider">New Provider</SelectItem>
```

### 2. Update Agent Builder Function

Edit `livekit_agent/src/pipeline.py`:

```python
def build_stt_dynamic(config: dict):
    provider = config.get("stt", "deepgram")
    
    # ... existing providers ...
    
    elif provider == "new_provider":
        return new_provider.STT(
            model=config.get("stt_model", "default-model"),
            api_key=keys.get("new_provider", os.getenv("NEW_PROVIDER_API_KEY")),
        )
    else:
        raise ValueError(f"Unknown STT provider: {provider}")
```

### 3. Install Plugin

Add to `livekit_agent/requirements.txt`:

```
livekit-plugins-new_provider
```

### 4. Set Environment Variable

Add to `.env`:

```
NEW_PROVIDER_API_KEY=your_api_key
```

## Testing

### Test in Development

```bash
# Terminal 1: Start backend services
docker compose up livekit

# Terminal 2: Start frontend (from frontend directory)
npm run dev

# Terminal 3: Start agent (from livekit_agent directory)
python src/agent.py dev
```

Then visit `http://localhost:3000`, select models, and click "Start Call".

### Test Model Override

Change UI selection → Agent should immediately initialize with the new provider on next session.

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Unknown STT provider" error | Selected provider not implemented in agent | Check `build_stt_dynamic()`, add missing elif branch |
| Api key errors | Environment variable not set | Set `PROVIDER_API_KEY` in `.env` or docker-compose |
| Wrong model initialized | Config not passed to agent | Check `ctx.room.metadata` parsing in `agent.py` |
| Dropdown shows but no effect | Token not refreshed | Ensure `tokenSource` in `app.tsx` depends on `[stt, llm, tts]` |

## Summary

Model selection is achieved through:
1. **Frontend UI** captures user choice → passed to API
2. **Backend API** embeds choice in JWT metadata → sent to client
3. **Agent reads metadata** from room config → dynamically builds providers

This ensures runtime flexibility without rebuilding containers or restarting services.
