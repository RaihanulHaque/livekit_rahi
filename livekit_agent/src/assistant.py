from livekit.agents import Agent

DEFAULT_INSTRUCTIONS = """You are a helpful voice AI assistant. The user is interacting with you via voice, even if you perceive the conversation as text.
You eagerly assist users with their questions by providing information from your extensive knowledge.
Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
You are curious, friendly, and have a sense of humor."""


class Assistant(Agent):
    def __init__(self, instructions: str | None = None) -> None:
        super().__init__(instructions=instructions or DEFAULT_INSTRUCTIONS)

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="""Greet the user and offer your assistance.""",
            allow_interruptions=True,
        )
