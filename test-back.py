"""
test-back.py — Minimal SaaS backend simulator for agent_id fetch testing.

Usage:
    pip install fastapi uvicorn
    python test-back.py          # listens on http://0.0.0.0:8083

Endpoint:
    GET /api/v1/agents/{agent_id}
    → { agent_id, name, system_prompt }
"""

from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI(title="SaaS Backend Simulator", version="0.1.0")

# Hardcoded agent registry for testing
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
            "were loaded at session start via an HTTP call to the backend.\n"
            "- Keep responses under 3 sentences unless more detail is needed."
        ),
    },
}


@app.get("/api/v1/agents/{agent_id}")
def get_agent(agent_id: str):
    agent = AGENTS.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083, log_level="info")
