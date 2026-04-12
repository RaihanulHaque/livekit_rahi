"""
SIP Trunk and Dispatch Rule Manager with number mapping and Redis storage.

Handles dynamic registration and deletion of SIP phone numbers with user isolation.
Each user can provision multiple local phone numbers mapped to SIP trunks.

Storage format in Redis:
  Key: sip:{user_id}:{local_number}
  Value: {
    sip_number: "+1555...",
    trunk_id: "ST_xxx",
    dispatch_rule_id: "SDR_xxx",
    system_prompt: "...",
    stt: "deepgram",
    llm: "openai",
    tts: "elevenlabs",
    status: "active",
    created_at: timestamp
  }
"""

import json
import logging
import time
from typing import Optional

import redis
from livekit import api

logger = logging.getLogger("sip_manager")


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

        # Redis for persistent storage of trunk mappings
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

    def _storage_key(self, user_id: str, local_number: str) -> str:
        """Generate Redis storage key."""
        return f"sip:{user_id}:{local_number}"

    async def register_sip_trunk(
        self,
        user_id: str,
        local_number: str,
        system_prompt: str,
        stt: str,
        llm: str,
        tts: str,
        sip_number: Optional[str] = None,
    ) -> dict:
        """
        Register a new SIP trunk for a user.

        Args:
            user_id: User identifier (from JWT)
            local_number: Local phone number (without dashes, e.g., "09643234042")
            system_prompt: System prompt for the agent
            stt: STT provider (e.g., "deepgram")
            llm: LLM provider (e.g., "openai")
            tts: TTS provider (e.g., "elevenlabs")
            sip_number: Actual SIP number (e.g., "+15551234567"). If None, uses local_number.

        Returns:
            Dict with trunk_id, dispatch_rule_id, sip_number, status, etc.
        """
        # Use local_number as SIP number if not provided (simplest case)
        if sip_number is None:
            sip_number = f"+1{local_number}" if len(local_number) > 6 else f"+{local_number}"

        storage_key = self._storage_key(user_id, local_number)

        # Check if already exists
        existing = self.redis_client.get(storage_key)
        if existing:
            logger.warning(
                f"Trunk already exists for {local_number} (user {user_id}). Skipping."
            )
            return json.loads(existing)

        lkapi = await self._get_lkapi()

        try:
            # Create inbound trunk
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

            # Create dispatch rule with room metadata containing all config
            metadata = {
                "local_number": local_number,
                "system_prompt": system_prompt,
                "stt": stt,
                "llm": llm,
                "tts": tts,
            }
            room_metadata = json.dumps(metadata)

            room_prefix = f"sip-{user_id[:8]}-{local_number}-"

            rule = api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix=room_prefix,
                )
            )

            dispatch_request = api.CreateSIPDispatchRuleRequest(
                dispatch_rule=api.SIPDispatchRuleInfo(
                    rule=rule,
                    name=f"Dispatch: {local_number}",
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
            logger.info(f"Created dispatch rule {dispatch_rule_id} for {local_number}")

            # Store in Redis
            config = {
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
            self.redis_client.set(storage_key, json.dumps(config))
            logger.info(f"Stored config in Redis: {storage_key}")

            return config

        except Exception as e:
            logger.error(f"Failed to register SIP trunk: {e}")
            raise

    async def delete_sip_trunk(self, user_id: str, local_number: str) -> dict:
        """
        Delete a SIP trunk and dispatch rule.

        Args:
            user_id: User identifier
            local_number: Local phone number

        Returns:
            Dict with deleted=True and trunk details
        """
        storage_key = self._storage_key(user_id, local_number)

        # Get config from Redis
        config_str = self.redis_client.get(storage_key)
        if not config_str:
            raise ValueError(f"Trunk not found for {local_number}")

        config = json.loads(config_str)
        trunk_id = config["trunk_id"]
        dispatch_rule_id = config["dispatch_rule_id"]

        lkapi = await self._get_lkapi()

        try:
            # Delete dispatch rule first
            if dispatch_rule_id:
                await lkapi.sip.delete_sip_dispatch_rule(
                    api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=dispatch_rule_id)
                )
                logger.info(f"Deleted dispatch rule {dispatch_rule_id}")

            # Then delete trunk
            if trunk_id:
                await lkapi.sip.delete_sip_trunk(
                    api.DeleteSIPTrunkRequest(sip_trunk_id=trunk_id)
                )
                logger.info(f"Deleted trunk {trunk_id}")

            # Remove from Redis
            self.redis_client.delete(storage_key)
            logger.info(f"Removed from Redis: {storage_key}")

            return {
                "deleted": True,
                "local_number": local_number,
                "sip_number": config["sip_number"],
                "trunk_id": trunk_id,
            }

        except Exception as e:
            logger.error(f"Failed to delete SIP trunk: {e}")
            raise

    async def update_sip_trunk(
        self,
        user_id: str,
        local_number: str,
        system_prompt: Optional[str] = None,
        stt: Optional[str] = None,
        llm: Optional[str] = None,
        tts: Optional[str] = None,
    ) -> dict:
        """
        Update dispatch rule metadata (system prompt and provider config).

        Args:
            user_id: User identifier
            local_number: Local phone number
            system_prompt: New system prompt (optional)
            stt: New STT provider (optional)
            llm: New LLM provider (optional)
            tts: New TTS provider (optional)

        Returns:
            Updated config dict
        """
        storage_key = self._storage_key(user_id, local_number)

        # Get existing config
        config_str = self.redis_client.get(storage_key)
        if not config_str:
            raise ValueError(f"Trunk not found for {local_number}")

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
            "local_number": config["local_number"],
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
            self.redis_client.set(storage_key, json.dumps(config))
            logger.info(f"Updated config in Redis: {storage_key}")

            return config

        except Exception as e:
            logger.error(f"Failed to update SIP trunk: {e}")
            raise

    async def list_sip_trunks(self, user_id: str) -> list[dict]:
        """
        List all trunks for a user.

        Args:
            user_id: User identifier

        Returns:
            List of trunk configs
        """
        # Get all keys for this user
        pattern = self._storage_key(user_id, "*")
        keys = self.redis_client.keys(pattern)

        trunks = []
        for key in keys:
            config_str = self.redis_client.get(key)
            if config_str:
                trunks.append(json.loads(config_str))

        return trunks

    async def get_sip_trunk(self, user_id: str, local_number: str) -> dict:
        """
        Get a specific trunk config.

        Args:
            user_id: User identifier
            local_number: Local phone number

        Returns:
            Trunk config dict
        """
        storage_key = self._storage_key(user_id, local_number)
        config_str = self.redis_client.get(storage_key)

        if not config_str:
            raise ValueError(f"Trunk not found for {local_number}")

        return json.loads(config_str)
