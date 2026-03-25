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

4. Open http://localhost:3000

## Backend Modularity

The backend entrypoint is thin by design:

- livekit_agent/src/agent.py: runtime wiring and session start
- livekit_agent/src/assistant.py: assistant behavior and prompt attachment
- livekit_agent/src/pipeline.py: STT/LLM/TTS provider builders
- livekit_agent/src/system_prompt.py: domain prompt content

This split keeps provider swapping and future tool/plugin additions localized to pipeline and config layers.

## Environment Variables

Core variables:

- LIVEKIT_URL
- LIVEKIT_API_KEY
- LIVEKIT_API_SECRET
- DEEPGRAM_API_KEY
- OPENAI_API_KEY
- ELEVENLABS_API_KEY

Optional backend overrides:

- DEEPGRAM_MODEL
- DEEPGRAM_EAGER_EOT_THRESHOLD
- LLM_PROVIDER
- LLM_MODEL
- LLM_BASE_URL
- TTS_PROVIDER
- TTS_MODEL
- TTS_VOICE_ID

## Project Structure

```
.
├─ frontend/
├─ livekit_agent/
├─ .env.example
└─ docker-compose.yml
```

## Notes For Production

- Move from livekit --dev to a production LiveKit config.
- Add observability (metrics, traces, structured logs).
- Put secrets in a manager (not plain .env in CI/CD).
- Add CI checks for formatting, tests, and image builds.
