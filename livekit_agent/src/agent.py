import json
import logging
from livekit import api, rtc
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

    await ctx.connect()

    # Check if this is an outbound call (job metadata has phone_number)
    job_meta: dict = {}
    if ctx.job.metadata:
        try:
            job_meta = json.loads(ctx.job.metadata)
        except json.JSONDecodeError:
            pass

    phone_number: str | None = job_meta.get("phone_number")
    outbound_trunk_id: str | None = job_meta.get("outbound_trunk_id")
    is_outbound = bool(phone_number and outbound_trunk_id)

    if is_outbound:
        # Outbound: config comes from job metadata
        config = job_meta
    else:
        # Inbound: config comes from room metadata (set by dispatch rule)
        try:
            config = json.loads(ctx.room.metadata or "{}")
        except json.JSONDecodeError:
            config = {}

    system_prompt: str | None = config.get("system_prompt") or None

    if is_outbound:
        display_name = job_meta.get("display_name") or phone_number
        logger.info(f"Outbound call to {phone_number} via trunk {outbound_trunk_id}")

        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=outbound_trunk_id,
                    sip_call_to=phone_number,
                    participant_identity=phone_number,
                    participant_name=display_name,
                    krisp_enabled=True,
                    wait_until_answered=True,
                    play_dialtone=True,
                )
            )
            logger.info(f"Outbound call answered: {phone_number}")
        except api.TwirpError as e:
            logger.error(
                f"Outbound call failed: {e.message}, "
                f"SIP {e.metadata.get('sip_status_code')} {e.metadata.get('sip_status')}"
            )
            ctx.shutdown()
            return

        # Wait for SIP participant to fully join before starting session
        participant = await ctx.wait_for_participant(identity=phone_number)

        # Handle callee hanging up mid-call
        @ctx.room.on("participant_disconnected")
        def on_disconnect(p: rtc.RemoteParticipant):
            if p.identity == phone_number:
                logger.info(f"Callee {phone_number} disconnected, shutting down")
                ctx.shutdown()

        session = build_session(vad=ctx.proc.userdata["vad"], config=config)
        await session.start(
            agent=Assistant(instructions=system_prompt),
            room=ctx.room,
            participant=participant,
            room_options=room_io.RoomOptions(
                audio_input=_build_audio_input_options(),
            ),
        )
        # Outbound: let the callee speak first — no initial greeting

    else:
        # Inbound: existing flow unchanged
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
