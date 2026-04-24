"""
test-back.py — Minimal SaaS backend simulator for agent_id fetch testing.

Security:
    Requests must carry a LiveKit-signed JWT in the Authorization header.
    The agent signs the token with LIVEKIT_API_KEY / LIVEKIT_API_SECRET.
    This backend verifies the signature with the same pair — no extra secrets.

Usage:
    pip install fastapi uvicorn pyjwt python-dotenv
    LIVEKIT_API_KEY=devkey LIVEKIT_API_SECRET=secret python test-back.py

    Or with a .env file in the same directory:
    python test-back.py
"""

import os
import time

import jwt as pyjwt
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException

load_dotenv()

LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")

app = FastAPI(title="SaaS Backend Simulator", version="0.1.0")

# ---------------------------------------------------------------------------
# Auth dependency — verifies the Bearer token the agent sends
# ---------------------------------------------------------------------------

def verify_livekit_token(authorization: str = Header(default=None)) -> dict:
    """
    Verify that the request carries a valid LiveKit-signed JWT.

    The agent creates: jwt.encode({"iss": API_KEY, "exp": now+30}, API_SECRET, "HS256")
    We verify: signature valid + issuer matches our API key + not expired.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = authorization.removeprefix("Bearer ")
    try:
        payload = pyjwt.decode(
            token,
            LIVEKIT_API_SECRET,
            algorithms=["HS256"],
            options={"require": ["iss", "exp"]},
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    if payload.get("iss") != LIVEKIT_API_KEY:
        raise HTTPException(status_code=401, detail="Token issuer mismatch")

    return payload


# ---------------------------------------------------------------------------
# Hardcoded agent registry — replace with DB query in production
# ---------------------------------------------------------------------------

AGENTS: dict[str, dict] = {
    "2008011": {
        "agent_id": "2008011",
        "name": "Test Agent Alpha",
        "system_prompt": (
            "You are a highly capable AI assistant for Test Agent 2008011. "
            "Your system prompt was fetched dynamically from the SaaS backend — "
            "it was NOT embedded in the LiveKit JWT. "
            "This proves the agent_id flow works end-to-end.\n\n"
            "Behavior:\n"
            "- Greet the user warmly and mention you are Agent 2008011.\n"
            "- Answer questions concisely and professionally.\n"
            "- If asked about your configuration, explain that your instructions "
            "were loaded at session start via an authenticated HTTP call to the backend.\n"
            "- Keep responses under 3 sentences unless more detail is needed."
        ),
    },
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: str, _auth: dict = Depends(verify_livekit_token)):
    agent = AGENTS.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@app.get("/health")
def health():
    return {"status": "ok", "time": int(time.time())}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083, log_level="info")
