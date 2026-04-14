"""
LiveKit webhook receiver for SIP call lifecycle events.

Handles:
  - room_started  → create call record in Redis (call begins)
  - room_finished → compute duration, finalize call record (call ends)
  - participant_joined / participant_left → track who was in the call
  - participant_connection_aborted → track failed connections

Room metadata injected by SIPManager at dispatch rule creation:
  {
    "agent_id": "...",
    "local_number": "09643234042",
    "sip_number": "12707768622",
    "system_prompt": "...",
    "stt": "deepgram",
    "llm": "openai",
    "tts": "elevenlabs"
  }

Call records stored in Redis:
  Key:   call:{agent_id}:{room_name}
  Value: {
    room_name, agent_id, local_number, sip_number,
    started_at, ended_at, duration_seconds, status,
    participants_joined, participants_left
  }
"""

import json
import logging
import os
import time

import redis
from fastapi import APIRouter, HTTPException, Request, Response
from livekit.api import WebhookReceiver

logger = logging.getLogger("webhook_api")

router = APIRouter(prefix="/webhook", tags=["webhook"])

# ── LiveKit webhook receiver ──────────────────────────────────────────────────
_api_key = os.environ.get("LIVEKIT_API_KEY", "devkey")
_api_secret = os.environ.get("LIVEKIT_API_SECRET", "secret")
_receiver = WebhookReceiver(_api_secret)

# ── Redis client ──────────────────────────────────────────────────────────────
_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=os.environ.get("REDIS_HOST", "redis"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True,
        )
    return _redis


def _call_key(agent_id: str, room_name: str) -> str:
    return f"call:{agent_id}:{room_name}"


# ── Event handlers ────────────────────────────────────────────────────────────

def _handle_room_started(event) -> None:
    """
    Call began. Parse room metadata, store initial call record in Redis.
    Room name pattern: sip-{user_id[:8]}-{agent_id}-{random}
    """
    room = event.room
    room_name = room.name

    try:
        meta = json.loads(room.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    agent_id = meta.get("agent_id", "unknown")
    local_number = meta.get("local_number", "")
    sip_number = meta.get("sip_number", "")

    # creation_time is set by LiveKit when room was created (Unix seconds)
    started_at = room.creation_time if room.creation_time else int(time.time())

    record = {
        "room_name": room_name,
        "agent_id": agent_id,
        "local_number": local_number,
        "sip_number": sip_number,
        "started_at": started_at,
        "ended_at": None,
        "duration_seconds": None,
        "status": "active",
        "participants_joined": [],
        "participants_left": [],
    }

    key = _call_key(agent_id, room_name)
    _get_redis().set(key, json.dumps(record), ex=86400 * 30)  # 30-day TTL
    logger.info(
        "Call started | room=%s agent=%s local=%s sip=%s",
        room_name, agent_id, local_number, sip_number,
    )


def _handle_room_finished(event) -> None:
    """
    Call ended. Compute duration, mark call as completed in Redis.
    """
    room = event.room
    room_name = room.name

    try:
        meta = json.loads(room.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    agent_id = meta.get("agent_id", "unknown")
    local_number = meta.get("local_number", "")
    sip_number = meta.get("sip_number", "")

    ended_at = event.created_at if event.created_at else int(time.time())
    started_at = room.creation_time if room.creation_time else ended_at
    duration_seconds = max(0, ended_at - started_at)

    key = _call_key(agent_id, room_name)
    r = _get_redis()
    existing = r.get(key)

    if existing:
        record = json.loads(existing)
    else:
        # room_started event may have been missed — reconstruct
        record = {
            "room_name": room_name,
            "agent_id": agent_id,
            "local_number": local_number,
            "sip_number": sip_number,
            "started_at": started_at,
            "participants_joined": [],
            "participants_left": [],
        }

    record["ended_at"] = ended_at
    record["duration_seconds"] = duration_seconds
    record["status"] = "completed"
    r.set(key, json.dumps(record), ex=86400 * 30)

    logger.info(
        "====== CALL ENDED ====== room=%s | agent=%s | local=%s | duration=%ds | status=completed",
        room_name, agent_id, local_number, duration_seconds,
    )


def _handle_participant_joined(event) -> None:
    """Track participant joining the call room."""
    room = event.room
    participant = event.participant

    try:
        meta = json.loads(room.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    agent_id = meta.get("agent_id", "unknown")
    identity = participant.identity if participant else "unknown"
    kind = str(participant.kind) if participant else "unknown"

    logger.info(
        "Participant joined | room=%s agent=%s identity=%s kind=%s",
        room.name, agent_id, identity, kind,
    )

    key = _call_key(agent_id, room.name)
    r = _get_redis()
    existing = r.get(key)
    if existing:
        record = json.loads(existing)
        record.setdefault("participants_joined", []).append({
            "identity": identity,
            "kind": kind,
            "joined_at": int(time.time()),
        })
        r.set(key, json.dumps(record), ex=86400 * 30)


def _handle_participant_left(event) -> None:
    """Track participant leaving the call room."""
    room = event.room
    participant = event.participant

    try:
        meta = json.loads(room.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    agent_id = meta.get("agent_id", "unknown")
    identity = participant.identity if participant else "unknown"

    logger.info(
        "====== PARTICIPANT LEFT ====== room=%s | agent=%s | identity=%s",
        room.name, agent_id, identity,
    )

    key = _call_key(agent_id, room.name)
    r = _get_redis()
    existing = r.get(key)
    if existing:
        record = json.loads(existing)
        record.setdefault("participants_left", []).append({
            "identity": identity,
            "left_at": int(time.time()),
        })
        r.set(key, json.dumps(record), ex=86400 * 30)


def _handle_participant_connection_aborted(event) -> None:
    """Track aborted connections — media never established."""
    room = event.room
    participant = event.participant

    try:
        meta = json.loads(room.metadata or "{}")
    except json.JSONDecodeError:
        meta = {}

    agent_id = meta.get("agent_id", "unknown")
    identity = participant.identity if participant else "unknown"

    logger.warning(
        "====== CALL ABORTED ====== room=%s | agent=%s | identity=%s",
        room.name, agent_id, identity,
    )

    key = _call_key(agent_id, room.name)
    r = _get_redis()
    existing = r.get(key)
    if existing:
        record = json.loads(existing)
        record["status"] = "aborted"
        record["ended_at"] = int(time.time())
        started_at = record.get("started_at", record["ended_at"])
        record["duration_seconds"] = max(0, record["ended_at"] - started_at)
        r.set(key, json.dumps(record), ex=86400 * 30)


# ── Event dispatch table ──────────────────────────────────────────────────────
# Only handle call-disconnect events. All others are silently ignored.
_HANDLERS = {
    "room_started": _handle_room_started,
    "room_finished": _handle_room_finished,
    "participant_left": _handle_participant_left,
    "participant_connection_aborted": _handle_participant_connection_aborted,
}


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("")
async def receive_webhook(request: Request):
    """
    Receive and validate a LiveKit webhook event.

    LiveKit sends:
      POST /webhook
      Content-Type: application/webhook+json
      Authorization: Bearer <jwt-with-sha256-hash>
      Body: JSON-encoded WebhookEvent

    Validates the JWT signature, dispatches to the correct handler,
    stores call lifecycle data in Redis.
    """
    body = await request.body()
    auth_header = request.headers.get("Authorization", "")

    try:
        event = _receiver.receive(body.decode("utf-8"), auth_header)
    except Exception as e:
        logger.warning("Webhook signature validation failed: %s", e)
        raise HTTPException(status_code=401, detail=f"Invalid webhook signature: {e}")

    event_name = event.event

    handler = _HANDLERS.get(event_name)
    if handler:
        try:
            handler(event)
        except Exception as e:
            logger.error("Error in webhook handler for %s: %s", event_name, e)
    # else: silently ignore non-disconnect events (track_published, egress_*, etc.)

    return Response(content="Webhoooooook is implemented.", media_type="text/plain")
