"""
SIP Agent-to-Number Manager with exclusive number assignment and Redis storage.

Handles agent provisioning with dedicated phone numbers (local ↔ SIP mapping).
Each agent owns ONE local/SIP number pair. Numbers can be reassigned to different agents.

Storage format in Redis:
  Key: agent:{user_id}:{agent_id}
  Value: {
    local_number: "09643234042",
    sip_number: "12707768622",
    trunk_id: "ST_xxx",
    dispatch_rule_id: "SDR_xxx",
    system_prompt: "...",
    stt: "deepgram",
    llm: "openai",
    tts: "elevenlabs",
    status: "active",
    created_at: timestamp
  }

  Key: sip:{user_id}:{sip_number}
  Value: agent_id  (tracks which agent owns this number)
"""

import json
import logging
import os
import time
from typing import Optional

import redis
from livekit import api

logger = logging.getLogger("sip_manager")
OUTBOUND_AGENT_NAME = os.environ.get("OUTBOUND_AGENT_NAME", "")


class SIPManager:
    def __init__(
        self,
        livekit_url: str,
        livekit_api_key: str,
        livekit_api_secret: str,
        redis_host: str = "redis",
        redis_port: int = 6379,
    ):
        self.livekit_url = livekit_url
        self.livekit_api_key = livekit_api_key
        self.livekit_api_secret = livekit_api_secret

        # Redis for persistent storage
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
        )

        # LiveKit API client
        self._lkapi: Optional[api.LiveKitAPI] = None

    async def _get_lkapi(self) -> api.LiveKitAPI:
        """Lazy initialize LiveKit API client."""
        if self._lkapi is None:
            self._lkapi = api.LiveKitAPI(
                url=self.livekit_url,
                api_key=self.livekit_api_key,
                api_secret=self.livekit_api_secret,
            )
        return self._lkapi

    async def close(self):
        """Close LiveKit API client."""
        if self._lkapi:
            await self._lkapi.aclose()
            self._lkapi = None

    def _agent_key(self, user_id: str, agent_id: str) -> str:
        """Generate Redis key for agent."""
        return f"agent:{user_id}:{agent_id}"

    def _sip_owner_key(self, user_id: str, sip_number: str) -> str:
        """Generate Redis key for SIP number ownership tracking."""
        return f"sip:{user_id}:{sip_number}:owner"

    async def register_agent(
        self,
        user_id: str,
        agent_id: str,
        local_number: str,
        sip_number: str,
        system_prompt: str,
        stt: str,
        llm: str,
        tts: str,
    ) -> dict:
        """
        Register or update an agent with a dedicated phone number.

        Args:
            user_id: User identifier (from JWT)
            agent_id: Unique agent identifier
            local_number: Local phone number (e.g., "09643234042")
            sip_number: SIP provider number (e.g., "12707768622") - REQUIRED, user-provided
            system_prompt: System prompt for the agent
            stt: STT provider (e.g., "deepgram")
            llm: LLM provider (e.g., "openai")
            tts: TTS provider (e.g., "elevenlabs")

        Returns:
            Dict with agent config, trunk_id, dispatch_rule_id, status, etc.
        """
        if not sip_number:
            raise ValueError("sip_number is required and must be provided by user")

        agent_key = self._agent_key(user_id, agent_id)
        sip_owner_key = self._sip_owner_key(user_id, sip_number)

        # Check if this agent already has a number assigned - if different, detach old one
        existing_agent = self.redis_client.get(agent_key)
        if existing_agent:
            old_config = json.loads(existing_agent)
            if old_config["sip_number"] != sip_number:
                # Agent is being reassigned to a different number
                await self._detach_number_from_agent(
                    user_id, agent_id, old_config["sip_number"]
                )
                logger.info(
                    f"Detached agent {agent_id} from number {old_config['sip_number']}"
                )

        # Check if this SIP number is already owned by a different agent
        current_owner = self.redis_client.get(sip_owner_key)
        if current_owner and current_owner != agent_id:
            # Number is owned by different agent - detach from them
            await self._detach_number_from_agent(user_id, current_owner, sip_number)
            logger.info(f"Detached agent {current_owner} from number {sip_number}")

        lkapi = await self._get_lkapi()

        try:
            trunk_id = None
            dispatch_rule_id = None

            # Check if trunk already exists for this SIP number
            existing_trunks = await lkapi.sip.list_sip_inbound_trunk(
                api.ListSIPInboundTrunkRequest()
            )
            existing_trunk = None
            for trunk in existing_trunks.items:
                if sip_number in trunk.numbers:
                    existing_trunk = trunk
                    trunk_id = trunk.sip_trunk_id
                    break

            # Create trunk only if it doesn't exist
            if not existing_trunk:
                trunk = api.SIPInboundTrunkInfo(
                    name=f"Trunk: {local_number}",
                    numbers=[sip_number],
                    krisp_enabled=True,
                )
                created_trunk = await lkapi.sip.create_sip_inbound_trunk(
                    api.CreateSIPInboundTrunkRequest(trunk=trunk)
                )
                trunk_id = created_trunk.sip_trunk_id
                logger.info(f"Created trunk {trunk_id} for {sip_number}")
            else:
                logger.info(f"Reusing existing trunk {trunk_id} for {sip_number}")

            # Create dispatch rule with agent config
            metadata = {
                "agent_id": agent_id,
                "local_number": local_number,
                "sip_number": sip_number,
                "system_prompt": system_prompt,
                "stt": stt,
                "llm": llm,
                "tts": tts,
            }
            room_metadata = json.dumps(metadata)

            room_prefix = f"sip-{user_id[:8]}-{agent_id}-"

            rule = api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=room_prefix,
                )
            )

            dispatch_request = api.CreateSIPDispatchRuleRequest(
                dispatch_rule=api.SIPDispatchRuleInfo(
                    rule=rule,
                    name=f"Dispatch: {agent_id}",
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
                ),
            )

            created_rule = await lkapi.sip.create_sip_dispatch_rule(dispatch_request)
            dispatch_rule_id = created_rule.sip_dispatch_rule_id
            logger.info(f"Created dispatch rule {dispatch_rule_id} for {agent_id}")

            # Store agent config in Redis
            config = {
                "agent_id": agent_id,
                "local_number": local_number,
                "sip_number": sip_number,
                "trunk_id": trunk_id,
                "dispatch_rule_id": dispatch_rule_id,
                "system_prompt": system_prompt,
                "stt": stt,
                "llm": llm,
                "tts": tts,
                "status": "active",
                "created_at": int(time.time()),
            }
            self.redis_client.set(agent_key, json.dumps(config))
            # Track ownership of this SIP number
            self.redis_client.set(sip_owner_key, agent_id)
            logger.info(f"Registered agent {agent_id} with number {sip_number}")

            return config

        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            raise

    async def _detach_number_from_agent(
        self, user_id: str, agent_id: str, sip_number: str
    ) -> None:
        """Detach a SIP number from an agent (cleanup)."""
        agent_key = self._agent_key(user_id, agent_id)
        sip_owner_key = self._sip_owner_key(user_id, sip_number)

        # Remove from ownership tracking
        self.redis_client.delete(sip_owner_key)

        # Note: We DON'T delete the agent key here - just clear the number reference
        # The agent is effectively "numberless" until reassigned
        agent_data = self.redis_client.get(agent_key)
        if agent_data:
            config = json.loads(agent_data)
            config["sip_number"] = None
            config["status"] = "unassigned"
            self.redis_client.set(agent_key, json.dumps(config))

        logger.info(f"Detached number {sip_number} from agent {agent_id}")

    async def delete_agent(self, user_id: str, agent_id: str) -> dict:
        """
        Delete an agent and unassign their SIP number.

        Args:
            user_id: User identifier
            agent_id: Agent identifier

        Returns:
            Dict with deleted=True and agent details
        """
        agent_key = self._agent_key(user_id, agent_id)

        # Get agent config from Redis
        config_str = self.redis_client.get(agent_key)
        if not config_str:
            raise ValueError(f"Agent not found: {agent_id}")

        config = json.loads(config_str)
        dispatch_rule_id = config.get("dispatch_rule_id")
        sip_number = config.get("sip_number")

        lkapi = await self._get_lkapi()

        try:
            # Delete dispatch rule
            if dispatch_rule_id:
                await lkapi.sip.delete_sip_dispatch_rule(
                    api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=dispatch_rule_id)
                )
                logger.info(f"Deleted dispatch rule {dispatch_rule_id}")

            # Note: We DON'T delete the trunk here - it might be reused by other agents
            # Trunks are permanent and tied to provider numbers

            # Detach number from agent
            if sip_number:
                await self._detach_number_from_agent(user_id, agent_id, sip_number)

            # Remove agent from Redis
            self.redis_client.delete(agent_key)
            logger.info(f"Deleted agent {agent_id}")

            return {
                "deleted": True,
                "agent_id": agent_id,
                "local_number": config.get("local_number"),
                "sip_number": sip_number,
            }

        except Exception as e:
            logger.error(f"Failed to delete agent: {e}")
            raise

    async def update_agent(
        self,
        user_id: str,
        agent_id: str,
        system_prompt: Optional[str] = None,
        stt: Optional[str] = None,
        llm: Optional[str] = None,
        tts: Optional[str] = None,
    ) -> dict:
        """
        Update agent configuration (system prompt and provider config).

        Args:
            user_id: User identifier
            agent_id: Agent identifier
            system_prompt: New system prompt (optional)
            stt: New STT provider (optional)
            llm: New LLM provider (optional)
            tts: New TTS provider (optional)

        Returns:
            Updated agent config dict
        """
        agent_key = self._agent_key(user_id, agent_id)

        # Get existing config
        config_str = self.redis_client.get(agent_key)
        if not config_str:
            raise ValueError(f"Agent not found: {agent_id}")

        config = json.loads(config_str)
        dispatch_rule_id = config["dispatch_rule_id"]

        # Update provided fields
        if system_prompt is not None:
            config["system_prompt"] = system_prompt
        if stt is not None:
            config["stt"] = stt
        if llm is not None:
            config["llm"] = llm
        if tts is not None:
            config["tts"] = tts

        # Update dispatch rule with new metadata
        metadata = {
            "agent_id": config["agent_id"],
            "local_number": config["local_number"],
            "sip_number": config["sip_number"],
            "system_prompt": config["system_prompt"],
            "stt": config["stt"],
            "llm": config["llm"],
            "tts": config["tts"],
        }
        room_metadata = json.dumps(metadata)

        lkapi = await self._get_lkapi()

        try:
            # Get existing rule to preserve other fields
            rules = await lkapi.sip.list_sip_dispatch_rule(
                api.ListSIPDispatchRuleRequest()
            )
            existing_rule = None
            for rule in rules.items:
                if rule.sip_dispatch_rule_id == dispatch_rule_id:
                    existing_rule = rule
                    break

            if not existing_rule:
                raise ValueError(f"Dispatch rule {dispatch_rule_id} not found")

            # Create updated rule
            updated_rule_info = api.SIPDispatchRuleInfo(
                sip_dispatch_rule_id=dispatch_rule_id,
                name=existing_rule.name,
                trunk_ids=existing_rule.trunk_ids,
                rule=existing_rule.rule,
                room_config=api.RoomConfiguration(
                    metadata=room_metadata,
                    agents=existing_rule.room_config.agents
                    if existing_rule.room_config
                    else [],
                ),
            )

            await lkapi.sip.create_sip_dispatch_rule(
                api.CreateSIPDispatchRuleRequest(dispatch_rule=updated_rule_info)
            )
            logger.info(f"Updated dispatch rule {dispatch_rule_id}")

            # Update Redis
            self.redis_client.set(agent_key, json.dumps(config))
            logger.info(f"Updated agent {agent_id} in Redis")

            return config

        except Exception as e:
            logger.error(f"Failed to update agent: {e}")
            raise

    async def list_agents(self, user_id: str) -> list[dict]:
        """
        List all agents for a user.

        Args:
            user_id: User identifier

        Returns:
            List of agent configs
        """
        # Get all agent keys for this user
        pattern = self._agent_key(user_id, "*")
        keys = self.redis_client.keys(pattern)

        agents = []
        for key in keys:
            config_str = self.redis_client.get(key)
            if config_str:
                agents.append(json.loads(config_str))

        return agents

    async def get_agent(self, user_id: str, agent_id: str) -> dict:
        """
        Get a specific agent config.

        Args:
            user_id: User identifier
            agent_id: Agent identifier

        Returns:
            Agent config dict
        """
        agent_key = self._agent_key(user_id, agent_id)
        config_str = self.redis_client.get(agent_key)

        if not config_str:
            raise ValueError(f"Agent not found: {agent_id}")

        return json.loads(config_str)

    async def start_outbound_call(
        self,
        user_id: str,
        agent_id: str,
        phone_number: str,
        outbound_trunk_id: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> dict:
        """
        Start an outbound SIP call for an existing agent profile.

        The room metadata reuses the same shape as inbound/web so the active
        agent runtime can build the session without a separate codepath.
        """
        if not phone_number:
            raise ValueError("phone_number is required")

        config = await self.get_agent(user_id=user_id, agent_id=agent_id)
        trunk_id = outbound_trunk_id or os.environ.get("DEFAULT_OUTBOUND_TRUNK_ID")
        if not trunk_id:
            raise ValueError(
                "outbound_trunk_id is required when DEFAULT_OUTBOUND_TRUNK_ID is not configured"
            )

        room_name = f"outbound-{user_id[:8]}-{agent_id}-{int(time.time())}"
        participant_identity = f"outbound-{int(time.time() * 1000)}"

        room_metadata = {
            "agent_id": config["agent_id"],
            "local_number": config["local_number"],
            "sip_number": config["sip_number"],
            "system_prompt": config["system_prompt"],
            "stt": config["stt"],
            "llm": config["llm"],
            "tts": config["tts"],
            "call_direction": "outbound",
            "phone_number": phone_number,
            "outbound_trunk_id": trunk_id,
            "participant_identity": participant_identity,
            "participant_name": config["agent_id"],
            "display_name": display_name,
        }

        dispatch_metadata = {
            "call_direction": "outbound",
            "phone_number": phone_number,
            "outbound_trunk_id": trunk_id,
            "participant_identity": participant_identity,
            "participant_name": config["agent_id"],
            "display_name": display_name,
        }

        lkapi = await self._get_lkapi()

        try:
            await lkapi.room.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    metadata=json.dumps(room_metadata),
                    empty_timeout=60 * 5,
                    departure_timeout=20,
                )
            )

            dispatch = await lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=OUTBOUND_AGENT_NAME,
                    room=room_name,
                    metadata=json.dumps(dispatch_metadata),
                )
            )

            logger.info(
                "Started outbound call dispatch %s for agent %s to %s",
                dispatch.id,
                agent_id,
                phone_number,
            )

            return {
                "agent_id": agent_id,
                "room_name": room_name,
                "dispatch_id": dispatch.id,
                "dispatch_state": str(dispatch.state),
                "agent_name": OUTBOUND_AGENT_NAME,
                "phone_number": phone_number,
                "outbound_trunk_id": trunk_id,
                "participant_identity": participant_identity,
                "call_direction": "outbound",
            }
        except Exception as e:
            logger.error(f"Failed to start outbound call: {e}")
            raise
