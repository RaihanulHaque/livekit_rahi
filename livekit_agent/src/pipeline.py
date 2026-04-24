import os

from dotenv import load_dotenv

from livekit.agents import AgentSession, TurnHandlingOptions
from livekit.plugins import deepgram, elevenlabs, openai, groq, langchain, google
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from langgraph_agent import graph_app
import uuid

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
        return deepgram.STTv2(
            model=config.get("stt_model", os.getenv("DEEPGRAM_MODEL", "flux-general-en")),
            eager_eot_threshold=float(os.getenv("DEEPGRAM_EAGER_EOT_THRESHOLD", "0.4")),
            api_key=keys.get("deepgram", os.getenv("DEEPGRAM_API_KEY")),
        )
    elif provider == "elevenlabs":
        return elevenlabs.STT(
            model_id="scribe_v2_realtime",
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
        return elevenlabs.TTS(
            voice_id=config.get("tts_voice_id", os.getenv("TTS_VOICE_ID", "iP95p4xoKVk53GoZ742B")),
            model=config.get("tts_model", os.getenv("TTS_MODEL", "eleven_flash_v2_5")),
            api_key=keys.get("elevenlabs", os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")),
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