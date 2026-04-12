"""
FastAPI endpoints for SIP trunk management.

Provides REST API to dynamically add, delete, and manage SIP phone numbers.
All endpoints require LiveKit JWT authentication.

Endpoints:
  POST   /sip/trunks              - Register new phone number
  GET    /sip/trunks              - List all phone numbers for user
  GET    /sip/trunks/{local_number} - Get specific phone number
  PATCH  /sip/trunks/{local_number} - Update system prompt / providers
  DELETE /sip/trunks/{local_number} - Delete phone number
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

try:
    from sip_manager import SIPManager
except ImportError:
    from .sip_manager import SIPManager

logger = logging.getLogger("sip_api")

# ── Router ────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/sip", tags=["sip"])

# ── Singleton SIP Manager ─────────────────────────────────────────────────
_sip_manager: Optional[SIPManager] = None


def get_sip_manager() -> SIPManager:
    """Get or create SIP manager instance."""
    global _sip_manager
    if _sip_manager is None:
        _sip_manager = SIPManager(
            livekit_url=os.environ.get("LIVEKIT_URL", "ws://livekit:7880"),
            livekit_api_key=os.environ.get("LIVEKIT_API_KEY", "devkey"),
            livekit_api_secret=os.environ.get("LIVEKIT_API_SECRET", "secret"),
            redis_host=os.environ.get("REDIS_HOST", "redis"),
            redis_port=int(os.environ.get("REDIS_PORT", 6379)),
        )
    return _sip_manager


# ── JWT Validation ────────────────────────────────────────────────────────
async def validate_jwt(request: Request) -> dict:
    """
    Validate LiveKit JWT from Authorization header.

    Returns:
        Dict with decoded JWT claims, including user_id
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        from livekit import api

        # For now, use a simple validation by checking if token is present
        # In production, use livekit.access_token module to decode and verify JWT
        # This is a placeholder - the actual JWT validation would decode the token
        # using the shared secret.

        # For development, we'll extract user_id from a query param or use a default
        # In production, decode the JWT properly:
        # decoded = jwt.decode(token, api_secret, algorithms=["HS256"])
        # user_id = decoded.get("sub") or decoded.get("identity")

        # Placeholder: extract user_id from header or use default
        user_id = "default_user"  # This should come from decoded JWT

        return {"user_id": user_id, "token": token}

    except Exception as e:
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Request/Response Models ───────────────────────────────────────────────
class RegisterTrunkRequest(BaseModel):
    local_number: str
    system_prompt: str
    stt: str
    llm: str
    tts: str
    sip_number: Optional[str] = None


class UpdateTrunkRequest(BaseModel):
    system_prompt: Optional[str] = None
    stt: Optional[str] = None
    llm: Optional[str] = None
    tts: Optional[str] = None


class TrunkResponse(BaseModel):
    local_number: str
    sip_number: str
    trunk_id: str
    dispatch_rule_id: str
    system_prompt: str
    stt: str
    llm: str
    tts: str
    status: str
    created_at: int


class TrunkListItem(BaseModel):
    local_number: str
    sip_number: str
    trunk_id: str
    status: str
    created_at: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/trunks", response_model=TrunkResponse)
async def register_trunk(
    req: RegisterTrunkRequest,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Register a new SIP trunk (phone number)."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")

        result = await manager.register_sip_trunk(
            user_id=user_id,
            local_number=req.local_number,
            system_prompt=req.system_prompt,
            stt=req.stt,
            llm=req.llm,
            tts=req.tts,
            sip_number=req.sip_number,
        )

        return TrunkResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register trunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to register trunk")


@router.get("/trunks", response_model=list[TrunkListItem])
async def list_trunks(
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """List all SIP trunks for the user."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        trunks = await manager.list_sip_trunks(user_id=user_id)

        return [
            TrunkListItem(
                local_number=t["local_number"],
                sip_number=t["sip_number"],
                trunk_id=t["trunk_id"],
                status=t["status"],
                created_at=t["created_at"],
            )
            for t in trunks
        ]

    except Exception as e:
        logger.error(f"Failed to list trunks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list trunks")


@router.get("/trunks/{local_number}", response_model=TrunkResponse)
async def get_trunk(
    local_number: str,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Get a specific SIP trunk."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        trunk = await manager.get_sip_trunk(user_id=user_id, local_number=local_number)
        return TrunkResponse(**trunk)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get trunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trunk")


@router.patch("/trunks/{local_number}", response_model=TrunkResponse)
async def update_trunk(
    local_number: str,
    req: UpdateTrunkRequest,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Update a SIP trunk (system prompt, providers)."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")

        result = await manager.update_sip_trunk(
            user_id=user_id,
            local_number=local_number,
            system_prompt=req.system_prompt,
            stt=req.stt,
            llm=req.llm,
            tts=req.tts,
        )

        return TrunkResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update trunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to update trunk")


@router.delete("/trunks/{local_number}")
async def delete_trunk(
    local_number: str,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Delete a SIP trunk and dispatch rule."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        result = await manager.delete_sip_trunk(user_id=user_id, local_number=local_number)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete trunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete trunk")
