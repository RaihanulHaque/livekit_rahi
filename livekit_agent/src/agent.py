import json
import logging
import os
import time

import redis
from livekit import rtc
from livekit.agents import (
    AgentServer,
    JobContext,
    JobProcess,
    cli,
    room_io,
)
from livekit.plugins import (
    silero,
)

from assistant import Assistant
from pipeline import build_session

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("agent")


server = AgentServer(job_memory_warn_mb=1024)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def _get_redis() -> redis.Redis:
    return redis.Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        decode_responses=True,
    )


def _build_audio_input_options() -> room_io.AudioInputOptions:
    """
    Build audio input options for the agent.
    Noise cancellation is disabled for SIP endpoints as it causes audio
    degradation and prevents STT models from receiving proper audio context.
    """
    return room_io.AudioInputOptions()


@server.rtc_session()
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    await ctx.connect()

    try:
        config = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        config = {}

    system_prompt: str | None = config.get("system_prompt") or None
    agent_id = config.get("agent_id", "unknown")

    # If agent_id provided but no inline system_prompt, fetch from SaaS backend.
    # Request is authenticated with a short-lived JWT signed using the LiveKit
    # API secret — the same mechanism LiveKit uses for agent auth. The SaaS
    # backend verifies the signature with the same key pair it already holds.
    print(f"Agent config | agent_id={agent_id} | system_prompt={'present' if system_prompt else 'absent'}\n\n\n\n\n\n\n\n")
    logger.info("Agent config | agent_id=%s | system_prompt=%s\n\n\n\n", agent_id, "present" if system_prompt else "absent")
    if agent_id and agent_id != "unknown": # and not system_prompt:
        saas_url = os.environ.get("SAAS_BACKEND_URL", "").rstrip("/")
        if saas_url:
            try:
                import jwt as _jwt
                import httpx as _httpx

                lk_api_key = os.environ.get("LIVEKIT_API_KEY", "")
                lk_api_secret = os.environ.get("LIVEKIT_API_SECRET", "")
                auth_token = _jwt.encode(
                    {"iss": lk_api_key, "exp": int(time.time()) + 30},
                    lk_api_secret,
                    algorithm="HS256",
                )

                url = f"{saas_url}/api/v1/agents/{agent_id}"
                logger.info("Fetching system_prompt from SaaS | agent_id=%s | url=%s", agent_id, url)
                resp = _httpx.get(
                    # f"https://app.unisense.ai/api/v1/agents/{agent_id}",
                    url,
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=5,
                )
                if resp.status_code == 200:
                    system_prompt = resp.json().get("system_prompt") or None
                    logger.info(
                        "Fetched system_prompt from SaaS | agent_id=%s | length=%s",
                        agent_id,
                        len(system_prompt or ""),
                    )
                else:
                    logger.warning(
                        "SaaS backend returned %d for agent_id=%s", resp.status_code, agent_id
                    )
            except Exception as e:
                logger.warning(
                    "Failed to fetch agent config from SaaS | agent_id=%s | error=%s", agent_id, e
                )
    else:
        print("No agent_id provided in room metadata; using defaults\n\n\n")
        logger.warning("No agent_id provided in room metadata; using defaults\n\n\n")
    local_number = config.get("local_number", "")
    sip_number = config.get("sip_number", "")
    room_name = ctx.room.name
    started_at = int(time.time())

    session = build_session(vad=ctx.proc.userdata["vad"], config=config)

    # ── Transcript capture ────────────────────────────────────────────────
    # Each room runs in its own forked process — no shared state concerns.
    # Format matches the target API: {"role": "...", "content": "...", "total_tokens": 0}
    transcript: list[dict] = []

    @session.on("user_input_transcribed")
    def on_user_speech(ev):
        if ev.is_final and ev.transcript.strip():
            transcript.append({
                "role": "user",
                "content": ev.transcript.strip(),
                "total_tokens": 0,
            })

    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        item = ev.item
        # Guard against non-text items (AgentHandoff, function calls, tool results)
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

    @session.on("close")
    def on_session_close(ev):
        # Persist transcript to Redis under the call record key.
        try:
            r = _get_redis()
            call_key = f"call:{agent_id}:{room_name}"
            existing = r.get(call_key)

            if existing:
                record = json.loads(existing)
            else:
                record = {
                    "room_name": room_name,
                    "agent_id": agent_id,
                }

            record["transcript"] = transcript
            r.set(call_key, json.dumps(record), ex=86400 * 30)
            logger.info(
                "Transcript saved to Redis | room=%s | turns=%d",
                room_name, len(transcript),
            )
        except Exception as e:
            logger.error("Failed to save transcript to Redis: %s", e)

        # Notify SaaS backend with transcript
        callback_url = os.environ.get("CALLBACK_WEBHOOK_URL", "")
        if callback_url:
            try:
                import httpx
                ended_at = int(time.time())
                resp = httpx.post(
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
                logger.info(
                    "Webhook POST → %s/api/v1/call-completed | status=%d | turns=%d",
                    callback_url, resp.status_code, len(transcript),
                )
            except Exception as e:
                logger.error("Webhook POST failed | url=%s | error=%s", callback_url, e)

    # ── Start session ─────────────────────────────────────────────────────

    await session.start(
        agent=Assistant(instructions=system_prompt),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=_build_audio_input_options(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
