import logging
import os
import json
from livekit import rtc
from livekit import api
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
OUTBOUND_AGENT_NAME = os.environ.get("OUTBOUND_AGENT_NAME", "telephony-outbound-agent")


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


def _parse_json_dict(raw: str | None) -> dict:
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _build_outbound_dial_info(room_config: dict, job_config: dict) -> dict:
    phone_number = job_config.get("phone_number") or room_config.get("phone_number")
    outbound_trunk_id = job_config.get("outbound_trunk_id") or room_config.get("outbound_trunk_id")

    return {
        "phone_number": phone_number,
        "outbound_trunk_id": outbound_trunk_id,
        "participant_identity": job_config.get("participant_identity")
        or room_config.get("participant_identity")
        or phone_number,
        "participant_name": job_config.get("participant_name")
        or room_config.get("participant_name")
        or "Outbound Callee",
        "display_name": job_config.get("display_name") or room_config.get("display_name"),
    }


async def _run_agent_session(ctx: JobContext, *, allow_outbound: bool) -> None:
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Establish full connection so that the agent can broadcast back LLM and TTS output
    await ctx.connect()

    config = _parse_json_dict(ctx.room.metadata)
    job_config = _parse_json_dict(ctx.job.metadata)
    dial_info = _build_outbound_dial_info(config, job_config)
    is_outbound = (
        allow_outbound
        and bool(dial_info["phone_number"])
        and bool(dial_info["outbound_trunk_id"])
    )

    system_prompt: str | None = config.get("system_prompt") or None

    if is_outbound:
        try:
            await ctx.api.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    room_name=ctx.room.name,
                    sip_trunk_id=dial_info["outbound_trunk_id"],
                    sip_call_to=dial_info["phone_number"],
                    participant_identity=dial_info["participant_identity"],
                    participant_name=dial_info["participant_name"],
                    wait_until_answered=True,
                    display_name=dial_info["display_name"],
                    krisp_enabled=True,
                )
            )
        except api.TwirpError as exc:
            logger.error(
                "Outbound call failed for room %s: %s (SIP %s %s)",
                ctx.room.name,
                exc.message,
                exc.metadata.get("sip_status_code"),
                exc.metadata.get("sip_status"),
            )
            ctx.shutdown()
            return

        await ctx.wait_for_participant(
            identity=dial_info["participant_identity"],
            kind=rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
        )

    session = build_session(vad=ctx.proc.userdata["vad"], config=config)

    await session.start(
        agent=Assistant(
            instructions=system_prompt,
            greet_first=not is_outbound,
        ),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=_build_audio_input_options(),
        ),
    )


@server.rtc_session()
async def my_agent(ctx: JobContext):
    await _run_agent_session(ctx, allow_outbound=False)


@server.rtc_session(agent_name=OUTBOUND_AGENT_NAME)
async def outbound_agent(ctx: JobContext):
    await _run_agent_session(ctx, allow_outbound=True)


if __name__ == "__main__":
    cli.run_app(server)
