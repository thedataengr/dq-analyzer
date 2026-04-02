from langgraph.graph import StateGraph, MessagesState, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
from langgraph.types import interrupt
import os
import operator
from typing import Annotated
from src.lc_tools import build_lc_tools
from src.prompts import DQ_AGENT_TOOL_PROMPT
from src.audit import log_fix_attempt

class DQAgentState(MessagesState):
    """Represents the mutable state for the DQ agent graph.

    Attributes:
        fix_history: Accumulates all fix attempts made during the session.

    """
    # Inherited: messages: Annotated[list, add_messages]
    fix_history: Annotated[list[dict], operator.add]

def build_dq_agent(inspector, db, ai_model=None) -> tuple:
    """Build the compiled DQ agent graph and its bound tools.

    Args:
        inspector: Database inspection helper used by the tool layer.
        db: Database client used for read and write operations.
        ai_model: Optional Gemini model name to override the default model.

    Returns:
        tuple: A `(compiled_graph, tools)` pair for the agent workflow.

    """
    # Build tools
    tools = build_lc_tools(inspector, db)

    # Build LLM with tools bound
    llm = ChatGoogleGenerativeAI(
        model=ai_model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite"),
        temperature=0,
        google_api_key=os.environ.get("GEMINI_API_KEY")
    )
    llm_with_tools = llm.bind_tools(tools)


    # Agent node
    def agent_node(state: DQAgentState) -> dict:
        """Invoke the LLM and return its next response message.

        Args:
            state: The current graph state containing the running message history.

        Returns:
            dict: A state update containing the newly generated AI message.

        """
        messages = [SystemMessage(content=DQ_AGENT_TOOL_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def fix_node(state: DQAgentState) -> dict:
        """Handle human approval for a proposed fix and record the outcome.

        Args:
            state: The current graph state containing the latest tool calls.

        Returns:
            dict: A state update with tool/AI messages and appended fix history.

        """

        last_message = state["messages"][-1]

        # Find the propose_fix tool call
        fix_tool_call = next(
            (tc for tc in last_message.tool_calls if tc["name"] == "propose_fix"), None
        )

        if not fix_tool_call:
            return {"messages": [AIMessage(content="No fix proposal found.")]}

        fix_data = fix_tool_call["args"]

        # Pause and get human decision
        decision = interrupt({
            "fix_data": fix_data,
            "question": "Approve this fix? (approve/reject)"
        })

        # Log the decision
        log_fix_attempt(
            table_name=fix_data["table_name"],
            fix_sql=fix_data["fix_sql"],
            decision=decision,
            issue_description=fix_data["issue_description"]
        )

        if decision == "approve":
            # Apply the fix
            db.run_write(fix_data["fix_sql"])
            return {
                "messages": [
                    ToolMessage(content=f"Fix approved and applied to {fix_data['table_name']} table.",
                                tool_call_id=fix_tool_call["id"]),
                    AIMessage(content=f"Fix applied to {fix_data['table_name']}.")
                ],
                "fix_history": [{**fix_data, "decision": "approved"}]
            }
        else:
            return {
                "messages": [
                    ToolMessage(content="Fix rejected.", tool_call_id=fix_tool_call["id"]),
                    AIMessage(content="Fix rejected. No changes made.")
                ],
                "fix_history": [{**fix_data, "decision": "rejected"}]
            }

    def route_tools(state: DQAgentState) -> str:
        """Route execution to the appropriate next node after an agent turn.

        Args:
            state: The current graph state after the latest agent response.

        Returns:
            str: `"fix_node"` when a fix needs approval, `"tools"` when regular
            tools should run, or `END` when no tool call is present.

        """
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            # Check if any tool call is propose_fix
            for tc in last_message.tool_calls:
                if tc["name"] == "propose_fix":
                    return "fix_node"
            return "tools"
        return END

    # Build graph
    workflow = StateGraph(DQAgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_node("fix_node", fix_node)

    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        route_tools,
        {
            "tools": "tools",
            "fix_node": "fix_node",
            END: END
        }
    )
    workflow.add_edge("tools", "agent")
    workflow.add_edge("fix_node", "agent")

    # Compile with memory checkpointer for conversation persistence
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    return graph, tools
