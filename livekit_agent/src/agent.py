import asyncio
import json
import logging
import os
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


def _get_outbound_meta(ctx: JobContext) -> dict | None:
    """Safely extract outbound call metadata from job. Returns None if not outbound."""
    try:
        job_metadata = getattr(getattr(ctx, "job", None), "metadata", None)
        if not job_metadata:
            return None
        meta = json.loads(job_metadata)
        if isinstance(meta, dict) and meta.get("phone_number") and meta.get("outbound_trunk_id"):
            return meta
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None


@server.rtc_session()
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    await ctx.connect()

    outbound_meta = _get_outbound_meta(ctx)

    if outbound_meta:
        # ── OUTBOUND CALL ─────────────────────────────────────────────
        config = outbound_meta
        system_prompt = config.get("system_prompt") or None
        phone_number = config["phone_number"]
        outbound_trunk_id = config["outbound_trunk_id"]
        display_name = config.get("display_name") or phone_number

        logger.info(f"Outbound call to {phone_number} via trunk {outbound_trunk_id}")

        # Create a standalone LiveKit API client (works across all SDK versions)
        lkapi = api.LiveKitAPI(
            url=os.environ.get("LIVEKIT_URL", "ws://livekit:7880"),
            api_key=os.environ.get("LIVEKIT_API_KEY", "devkey"),
            api_secret=os.environ.get("LIVEKIT_API_SECRET", "secret"),
        )

        try:
            await lkapi.sip.create_sip_participant(
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
        except Exception as e:
            logger.error(f"Outbound call failed: {e}")
            await lkapi.aclose()
            ctx.shutdown()
            return
        finally:
            await lkapi.aclose()

        # Wait for SIP participant to join the room
        participant = None
        try:
            participant = await ctx.wait_for_participant(identity=phone_number)
        except AttributeError:
            # Fallback: wait for participant via room events (older SDK)
            logger.info("wait_for_participant not available, using room event fallback")
            for p in ctx.room.remote_participants.values():
                if p.identity == phone_number:
                    participant = p
                    break
            if participant is None:
                wait_event = asyncio.Event()
                found_participant = {}

                @ctx.room.on("participant_connected")
                def _on_connect(p: rtc.RemoteParticipant):
                    if p.identity == phone_number:
                        found_participant["p"] = p
                        wait_event.set()

                try:
                    await asyncio.wait_for(wait_event.wait(), timeout=30)
                    participant = found_participant.get("p")
                except asyncio.TimeoutError:
                    logger.error(f"Timed out waiting for SIP participant {phone_number}")
                    ctx.shutdown()
                    return

        if participant is None:
            logger.error(f"SIP participant {phone_number} not found in room")
            ctx.shutdown()
            return

        # Handle callee hanging up
        @ctx.room.on("participant_disconnected")
        def on_disconnect(p: rtc.RemoteParticipant):
            if p.identity == phone_number:
                logger.info(f"Callee {phone_number} disconnected")
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
        # Outbound: callee speaks first — no initial greeting

    else:
        # ── INBOUND CALL (unchanged) ─────────────────────────────────
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
