from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_ollama import ChatOllama


document_content = ""  

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]



@tool
def update(content: str) -> str:
    """Replace the entire document with *content*."""
    global document_content
    document_content = content
    return f"✅ Document updated:\n{document_content}"


@tool
def save(filename: str) -> str:
    """Save the current document to *filename*.txt (UTF‑8)."""
    global document_content

    if not filename.endswith(".txt"):
        filename += ".txt"

    try:
        with open(filename, "w", encoding="utf-8") as fp:
            fp.write(document_content)
        return f"💾 Document saved to {filename}"
    except Exception as exc:
        return f"❌ Error while saving: {exc}"



TOOLS = [update, save]



llm = ChatOllama(model="llama3", tools=TOOLS)



def our_agent(state: AgentState) -> AgentState:
    """LangGraph node that calls the LLM and appends its response."""

    system_prompt = SystemMessage(
        content=
        (
            "You are **Drafter**, a helpful writing assistant.\n"
            "You MUST respond by calling exactly one of the available tools: 'update' or 'save'.\n"
            "After an 'update' call, always show the full updated document.\n"
            "After a successful 'save' call, say goodbye.\n"
            "Never answer with plain text that is not wrapped in a tool call.\n\n"
            f"Current document content (may be empty):\n{document_content}"
        )
    )

    messages_in = [system_prompt, *state["messages"]]
    response = llm.invoke(messages_in)

 
    print(f"\n🤖 {response.content}")
    if getattr(response, "tool_calls", None):
        print(f"🔧 Tool requested: {[tc['name'] for tc in response.tool_calls]}")

    return {"messages": [*state["messages"], response]}



def user_input(state: AgentState) -> AgentState:
    """LangGraph node that blocks until the user types a message."""
    text = input("\n🧑  ")
    hm = HumanMessage(content=text)
    return {"messages": [*state["messages"], hm]}



def should_continue(state: AgentState) -> str:
    """Return 'end' if a save operation occurred, else 'continue'."""
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage) and "saved" in msg.content.lower():
            return "end"
    return "continue"



graph = StateGraph(AgentState)

graph.add_node("agent", our_agent)

graph.add_node("user_input", user_input)

graph.add_node("tools", ToolNode(TOOLS))




graph.set_entry_point("agent")


graph.add_edge("agent", "user_input")     
graph.add_edge("user_input", "tools")      

graph.add_conditional_edges(
    "tools",
    should_continue,
    {
        "continue": "agent",  
        "end": END,            
    },
)

app = graph.compile()



def run_document_agent() -> None:
    print("\n===== DRAFTER =====")
    first_prompt = input("What would you like to do with the document? ")

    state: AgentState = {"messages": [HumanMessage(content=first_prompt)]}

    
    for step in app.stream(state, stream_mode="values"):
        
        for message in step.get("messages", []):
            if isinstance(message, ToolMessage):
                print(f"\n🛠️ {message.content}")

    print("\n===== DRAFTER FINISHED =====")


if __name__ == "__main__":
    run_document_agent()
