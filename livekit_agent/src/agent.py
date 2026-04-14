import json
import logging
import time

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

logger = logging.getLogger("agent")


server = AgentServer(job_memory_warn_mb=1024)


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


def _build_audio_input_options() -> room_io.AudioInputOptions:
    # Import noise cancellation lazily so setup/download commands can run
    # in environments where the optional native plugin cannot be loaded.
    try:
        from livekit.plugins import noise_cancellation
    except Exception as exc:
        logger.warning(
            "Noise cancellation plugin unavailable, continuing without it: %s",
            exc,
        )
        return room_io.AudioInputOptions()

    return room_io.AudioInputOptions(
        noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
        if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        else noise_cancellation.BVC(),
    )


@server.rtc_session()
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Establish full connection so that the agent can broadcast back LLM and TTS output
    await ctx.connect()

    try:
        config = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        config = {}

    system_prompt: str | None = config.get("system_prompt") or None

    session = build_session(vad=ctx.proc.userdata["vad"], config=config)

    # ── Transcript capture ────────────────────────────────────────────────
    transcript: list[dict] = []

    @session.on("user_input_transcribed")
    def on_user_speech(ev):
        if ev.is_final and ev.transcript.strip():
            entry = {
                "role": "user",
                "text": ev.transcript.strip(),
                "timestamp": time.time(),
            }
            transcript.append(entry)
            logger.info(
                "📞 [USER]: %s", ev.transcript.strip()
            )

    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        item = ev.item
        text = item.text_content if item.text_content else ""
        if not text.strip():
            return
        # Only capture assistant responses here (user captured via STT above)
        if item.role == "assistant":
            entry = {
                "role": "assistant",
                "text": text.strip(),
                "timestamp": time.time(),
            }
            transcript.append(entry)
            logger.info(
                "🤖 [AGENT]: %s", text.strip()
            )

    @session.on("close")
    def on_session_close(ev):
        if not transcript:
            logger.info("Session closed with no transcript.")
            return

        logger.info("=" * 60)
        logger.info("FULL CONVERSATION TRANSCRIPT")
        logger.info("Room: %s", ctx.room.name)
        logger.info("=" * 60)
        for entry in transcript:
            role_label = "USER " if entry["role"] == "user" else "AGENT"
            logger.info("[%s]: %s", role_label, entry["text"])
        logger.info("=" * 60)
        logger.info("Total turns: %d", len(transcript))
        logger.info("=" * 60)

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
