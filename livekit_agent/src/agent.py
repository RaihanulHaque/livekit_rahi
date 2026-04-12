import logging
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

    import json
    try:
        config = json.loads(ctx.room.metadata or "{}")
    except json.JSONDecodeError:
        config = {}

    system_prompt: str | None = config.get("system_prompt") or None

    session = build_session(vad=ctx.proc.userdata["vad"], config=config)

    await session.start(
        agent=Assistant(instructions=system_prompt),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=_build_audio_input_options(),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
