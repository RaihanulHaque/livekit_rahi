"""
Setup script to create SIP inbound trunks and dispatch rules per agent.

Each agent gets its own phone number, trunk, and dispatch rule.
The dispatch rule sets room metadata with the agent's config so the
Python agent knows which system prompt and providers to use.

Usage:
    docker compose exec livekit_agent python src/setup_sip.py

To add a new agent, add an entry to AGENT_PHONE_MAP below and re-run.
Existing trunks/rules are listed first so you can avoid duplicates.
"""

import asyncio
import json
import os

from livekit import api


LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://livekit:7880")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")

# ── Map each agent to its phone number and config ────────────────────────
# When a call comes in on a number, the dispatch rule sets room metadata
# with this config. The Python agent reads it exactly like a web call.
#
# The "system_prompt" can be the full prompt text (for prototyping) or
# an "agent_id" pointer that the agent resolves from an external API.
AGENT_PHONE_MAP = [
    {
        "name": "HVAC Support Agent",
        "phone": "+12707768622",
        "metadata": {
            "system_prompt": (
                "You are a professional HVAC support agent. "
                "Help callers with heating, ventilation, and air conditioning issues. "
                "Be concise and speak naturally for voice conversation."
            ),
            "stt": "deepgram",
            "llm": "openai",
            "tts": "elevenlabs",
        },
    },
    # Add more agents here:
    # {
    #     "name": "Sales Assistant",
    #     "phone": "+15551234567",
    #     "metadata": {
    #         "system_prompt": "You are a sales assistant...",
    #         "stt": "deepgram",
    #         "llm": "openai",
    #         "tts": "elevenlabs",
    #     },
    # },
]


async def main():
    lkapi = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    # ── List existing resources ──────────────────────────────────────────
    existing_trunks = await lkapi.sip.list_sip_inbound_trunk(
        api.ListSIPInboundTrunkRequest()
    )
    existing_rules = await lkapi.sip.list_sip_dispatch_rule(
        api.ListSIPDispatchRuleRequest()
    )

    print("=== Existing inbound trunks ===")
    for t in existing_trunks.items:
        print(f"  {t.sip_trunk_id}  numbers={t.numbers}  name={t.name}")
    if not existing_trunks.items:
        print("  (none)")

    print("\n=== Existing dispatch rules ===")
    for r in existing_rules.items:
        print(f"  {r.sip_dispatch_rule_id}  name={r.name}  trunks={r.trunk_ids}")
    if not existing_rules.items:
        print("  (none)")

    # ── Create trunk + dispatch rule for each agent ──────────────────────
    for agent_cfg in AGENT_PHONE_MAP:
        phone = agent_cfg["phone"]
        name = agent_cfg["name"]
        metadata = agent_cfg["metadata"]

        print(f"\n--- Setting up: {name} ({phone}) ---")

        # Check if trunk already exists for this number
        existing = [
            t for t in existing_trunks.items
            if phone in t.numbers
        ]
        if existing:
            print(f"  Trunk already exists for {phone}: {existing[0].sip_trunk_id}")
            print(f"  Skipping (delete it first if you want to recreate)")
            continue

        # Create inbound trunk
        trunk = api.SIPInboundTrunkInfo(
            name=f"Trunk: {name}",
            numbers=[phone],
            krisp_enabled=True,
        )
        created_trunk = await lkapi.sip.create_sip_inbound_trunk(
            api.CreateSIPInboundTrunkRequest(trunk=trunk)
        )
        trunk_id = created_trunk.sip_trunk_id
        print(f"  Created trunk: {trunk_id}")

        # Create dispatch rule with agent config as room metadata.
        # This is the key: the room metadata is identical in shape to
        # what the web frontend sends via JWT — so the Python agent
        # handles both paths with the same code.
        room_metadata = json.dumps(metadata)

        rule = api.SIPDispatchRule(
            dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                room_prefix=f"sip-{name.lower().replace(' ', '-')}-",
            )
        )

        dispatch_request = api.CreateSIPDispatchRuleRequest(
            dispatch_rule=api.SIPDispatchRuleInfo(
                rule=rule,
                name=f"Dispatch: {name}",
                trunk_ids=[trunk_id],
                room_config=api.RoomConfiguration(
                    metadata=room_metadata,
                    agents=[
                        api.RoomAgentDispatch(
                            agent_name="",
                            metadata="sip-inbound",
                        )
                    ],
                ),
            )
        )

        created_rule = await lkapi.sip.create_sip_dispatch_rule(dispatch_request)
        print(f"  Created dispatch rule: {created_rule.sip_dispatch_rule_id}")
        print(f"  Room prefix: sip-{name.lower().replace(' ', '-')}-")
        print(f"  Room metadata: {room_metadata}")

    await lkapi.aclose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
