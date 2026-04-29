import os

from dotenv import load_dotenv

from typing import Any

from livekit.agents import AgentSession, TurnHandlingOptions
from livekit.agents import tts as lk_tts
from livekit.plugins import deepgram, elevenlabs, openai, groq, langchain, google
from livekit.plugins.google import beta as google_beta
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from langgraph_agent import graph_app
import uuid


class ElevenLabsHTTPTTS(elevenlabs.TTS):
    """eleven_v3 doesn't support WebSocket /multi-stream-input (403).
    This subclass forces HTTP ChunkedStream path (streaming=False).
    TTFB ~0.7s vs ~0.2s for WebSocket models — acceptable trade-off.
    See: https://github.com/livekit/agents/issues/4901
    """
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._capabilities = lk_tts.TTSCapabilities(
            streaming=False,
            aligned_transcript=False,
        )

# Load local overrides for direct local runs (uv run src/agent.py dev).
load_dotenv()


def build_session(vad, config: dict = None) -> AgentSession:
    if config is None:
        config = {}
        
    return AgentSession(
        stt=build_stt_dynamic(config),
        llm=build_llm_dynamic(config),
        tts=build_tts_dynamic(config),
        # turn_detection=MultilingualModel(),
        turn_handling=TurnHandlingOptions(turn_detector=MultilingualModel()),
        vad=vad,
        preemptive_generation=True,
    )


def build_stt_dynamic(config: dict):
    provider = config.get("stt", "deepgram")
    keys = config.get("api_keys", {})

    if provider == "deepgram":
        # Default to nova-2-phonecall for SIP calls (8kHz audio), otherwise flux-general-en
        default_model = "nova-2-phonecall" if config.get("sip_number") else "flux-general-en"
        return deepgram.STTv2(
            model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", default_model)),
            # model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", "nova-3")), # This multiligual model isn't working well, switching back to flux-general-en for now
            eager_eot_threshold=float(os.getenv("DEEPGRAM_EAGER_EOT_THRESHOLD", "0.4")),
            api_key=keys.get("deepgram", os.getenv("DEEPGRAM_API_KEY")),
        )
    elif provider == "elevenlabs":
        return elevenlabs.STT(
            model_id="scribe_v2_realtime",
            language_code="bn",
            api_key=keys.get("elevenlabs", os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")),
        )
    elif provider == "whisper":
        return openai.STT(
            model=config.get("stt_model", "whisper-1"),
            api_key=keys.get("openai", os.getenv("OPENAI_API_KEY")),
        )
    else:
        raise ValueError(f"Unknown STT provider: {provider}")


def build_llm_dynamic(config: dict):
    provider = config.get("llm", "langchain")
    keys = config.get("api_keys", {})

    if provider == "openai":
        return openai.LLM(
            api_key=keys.get("openai", "http://host.docker.internal:1234/v1/"),
            model=config.get("llm_model", os.getenv("LLM_MODEL", "gpt-4o-mini")),
        )
    elif provider == "groq":
        return groq.LLM(
            model=config.get("llm_model", "openai/gpt-oss-120b"),
            api_key=keys.get("groq", os.getenv("GROQ_API_KEY")),
        )
    elif provider == "google":
        return google.LLM(
            model=config.get("llm_model", "gemini-3.1-flash-lite-preview"),
            api_key=keys.get("google", os.getenv("GEMINI_API_KEY")),
        )
    elif provider == "langchain":
        return build_llm_langchain(graph_app)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def build_tts_dynamic(config: dict):
    provider = config.get("tts", "elevenlabs")
    keys = config.get("api_keys", {})

    if provider == "elevenlabs":
        # model = config.get("tts_model", os.getenv("TTS_MODEL", "eleven_flash_v2_5"))
        model = config.get("tts_model", os.getenv("TTS_MODEL", "eleven_v3"))
        # voice_id = config.get("tts_voice_id", os.getenv("TTS_VOICE_ID", "iP95p4xoKVk53GoZ742B"))
        voice_id = config.get("tts_voice_id", os.getenv("TTS_VOICE_ID", "WiaIVvI1gDL4vT4y7qUU"))
        api_key = keys.get("elevenlabs", os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY"))
        cls = ElevenLabsHTTPTTS if model == "eleven_v3" else elevenlabs.TTS
        language = config.get("tts_language", os.getenv("TTS_LANGUAGE", "bn" if model == "eleven_v3" else None))
        kwargs = dict(voice_id=voice_id, model=model, api_key=api_key)
        if language:
            kwargs["language"] = language
        return cls(**kwargs)
    elif provider == "google":
        return google_beta.GeminiTTS(
            model="gemini-3.1-flash-tts-preview",
            voice_name=config.get("tts_voice_name", "Zephyr"),
            api_key=keys.get("google", os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")),
        )
    elif provider == "kokoro":
        # Uses local kokoro container overrides
        return build_tts_kokoro()
    elif provider == "openai":
        return openai.TTS(
            voice=config.get("tts_voice", "alloy"),
            api_key=keys.get("openai", os.getenv("OPENAI_API_KEY")),
        )
    else:
        raise ValueError(f"Unknown TTS provider: {provider}")

def build_llm_langchain(graph):
    config = {"configurable": {"thread_id": uuid.uuid4().hex}}
    return langchain.LLMAdapter(graph, config=config)


def build_tts_kokoro():
    return openai.TTS(
            base_url="http://kokoro:8880/v1",
            # base_url="http://localhost:8880/v1", # uncomment for local testing
            model="kokoro",
            voice="af_nova",
            api_key="no-key-needed"
        )