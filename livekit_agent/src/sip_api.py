"""
FastAPI endpoints for SIP agent management.

Provides REST API to dynamically add, delete, and manage SIP-enabled agents.
Each agent gets a dedicated local/SIP number pair. Numbers are exclusive to agents.
All endpoints require LiveKit JWT authentication.

Endpoints:
  POST   /sip/agents              - Register new agent with number
  GET    /sip/agents              - List all agents for user
  GET    /sip/agents/{agent_id}   - Get specific agent config
  PATCH  /sip/agents/{agent_id}   - Update agent config
  DELETE /sip/agents/{agent_id}   - Delete agent and free up number
"""

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
router = APIRouter(prefix="/sip", tags=["sip-agents"])

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

    # For development: accept requests with or without JWT
    # In production, implement proper JWT validation
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix
    else:
        token = None
        logger.warning("Request without Authorization header - using default user")

    # Placeholder: use default user for development
    user_id = "default_user"

    return {"user_id": user_id, "token": token}


# ── Request/Response Models ───────────────────────────────────────────────
class RegisterAgentRequest(BaseModel):
    agent_id: str
    local_number: str
    sip_number: str  # REQUIRED: user must provide their SIP number
    system_prompt: str
    stt: str
    llm: str
    tts: str


class UpdateAgentRequest(BaseModel):
    system_prompt: Optional[str] = None
    stt: Optional[str] = None
    llm: Optional[str] = None
    tts: Optional[str] = None


class AgentResponse(BaseModel):
    agent_id: str
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


class AgentListItem(BaseModel):
    agent_id: str
    local_number: str
    sip_number: str
    status: str
    created_at: int


class StartOutboundCallRequest(BaseModel):
    agent_id: str
    phone_number: str
    outbound_trunk_id: Optional[str] = None
    display_name: Optional[str] = None


class OutboundCallResponse(BaseModel):
    agent_id: str
    room_name: str
    dispatch_id: str
    dispatch_state: str
    agent_name: str
    phone_number: str
    outbound_trunk_id: str
    participant_identity: str
    call_direction: str


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/agents", response_model=AgentResponse)
async def register_agent(
    req: RegisterAgentRequest,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Register a new agent with a dedicated SIP number."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")

        result = await manager.register_agent(
            user_id=user_id,
            agent_id=req.agent_id,
            local_number=req.local_number,
            sip_number=req.sip_number,
            system_prompt=req.system_prompt,
            stt=req.stt,
            llm=req.llm,
            tts=req.tts,
        )

        return AgentResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to register agent")


@router.get("/agents", response_model=list[AgentListItem])
async def list_agents(
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """List all agents for the user."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        agents = await manager.list_agents(user_id=user_id)

        return [
            AgentListItem(
                agent_id=a["agent_id"],
                local_number=a["local_number"],
                sip_number=a["sip_number"],
                status=a["status"],
                created_at=a["created_at"],
            )
            for a in agents
        ]

    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Get a specific agent config."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        agent = await manager.get_agent(user_id=user_id, agent_id=agent_id)
        return AgentResponse(**agent)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent")


@router.patch("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    req: UpdateAgentRequest,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Update an agent's config (system prompt, providers)."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")

        result = await manager.update_agent(
            user_id=user_id,
            agent_id=agent_id,
            system_prompt=req.system_prompt,
            stt=req.stt,
            llm=req.llm,
            tts=req.tts,
        )

        return AgentResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to update agent")


@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Delete an agent and free up their SIP number."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        result = await manager.delete_agent(user_id=user_id, agent_id=agent_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")


@router.post("/outbound/call", response_model=OutboundCallResponse)
async def start_outbound_call(
    req: StartOutboundCallRequest,
    jwt_claims: dict = Depends(validate_jwt),
    manager: SIPManager = Depends(get_sip_manager),
):
    """Start an outbound SIP call using an existing agent profile."""
    try:
        user_id = jwt_claims.get("user_id", "default_user")
        result = await manager.start_outbound_call(
            user_id=user_id,
            agent_id=req.agent_id,
            phone_number=req.phone_number,
            outbound_trunk_id=req.outbound_trunk_id,
            display_name=req.display_name,
        )
        return OutboundCallResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start outbound call: {e}")
        raise HTTPException(status_code=500, detail="Failed to start outbound call")
