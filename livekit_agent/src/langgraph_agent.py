import os
import operator
from typing import Annotated, Sequence, TypedDict
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.tools import tool
# from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ==========================================
# 1. Define Tools
# ==========================================

@tool
def calculator(expression: str) -> str:
    """Evaluates simple mathematical expressions. Input should be a string like '2 + 2'."""
    try:
        # Using eval safely for basic math operations
        allowed_names = {"__builtins__": None}
        result = eval(expression, allowed_names, {})
        return str(result)
    except Exception as e:
        return f"Error calculating: {e}"

@tool
def get_weather(location: str) -> str:
    """Gets the current weather for a specified location."""
    # This is a mock response. You can replace this with a free API like OpenMeteo 
    # or a simple requests.get() call to a weather service later.
    return f"The weather in {location} is -5 degrees Celsius with light snow."

tools = [calculator, get_weather]

# Only enable Tavily when the API key is present so image build doesn't fail.
tavily_api_key = os.getenv("TAVILY_API_KEY")
if tavily_api_key:
    tools.append(TavilySearch(max_results=2))
else:
    logger.warning(
        "TAVILY_API_KEY is not set; web search tool is disabled."
    )

# ==========================================
# 2. Configure LM Studio (OpenAI Compatible)
# ==========================================

# By default, LM Studio runs on port 1234. Change the model name to whatever you have loaded.
llm = ChatOpenAI(
    base_url="http://host.docker.internal:1234/v1/",
    api_key="lm-studio", # LM Studio doesn't enforce keys, but LangChain requires the parameter
    model="local-model", # This is ignored by LM Studio, it uses the loaded model
    temperature=0.5
)

llm_with_tools = llm.bind_tools(tools)

# ==========================================
# 3. Build the LangGraph
# ==========================================

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

def call_model(state: AgentState):
    messages = state["messages"]
    
    # System prompt strictly designed for Text-to-Speech output
    system_prompt = SystemMessage(
        content="You are a helpful, conversational voice assistant. "
                "Always provide your answers in plain text. "
                "Do not use markdown, bullet points, asterisks, or long complex sentences. "
                "Keep your responses concise and natural for spoken audio."
    )
    
    # Prepend the system prompt to the message history
    response = llm_with_tools.invoke([system_prompt] + messages)
    return {"messages": [response]}

# Define the graph structure
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

# Set the entry point
workflow.add_edge(START, "agent")

# Add conditional routing: if the agent calls a tool, go to "tools", otherwise end.
workflow.add_conditional_edges(
    "agent",
    tools_condition,
)

# After tools run, go back to the agent to summarize the result
workflow.add_edge("tools", "agent")

# Add a checkpointer for memory (essential for multi-turn voice conversations)
memory = MemorySaver()
graph_app = workflow.compile(checkpointer=memory)

# ==========================================
# 4. Test the Loop
# ==========================================

if __name__ == "__main__":
    # We use a thread_id to keep track of the conversation history
    config = {"configurable": {"thread_id": "test_voice_session_1"}}
    
    print("Agent is ready. Type your query (or 'quit' to exit):")
    while True:
        user_input = input("User: ")
        if user_input.lower() in ['quit', 'exit']:
            break
            
        # Stream the graph updates
        for event in graph_app.stream({"messages": [HumanMessage(content=user_input)]}, config, stream_mode="values"):
            last_message = event["messages"][-1]
            # Only print the AI's final response, not the tool calls
            if last_message.type == "ai" and not last_message.tool_calls:
                print(f"Voice Assistant: {last_message.content}")