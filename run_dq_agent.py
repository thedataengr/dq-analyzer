import sys
import os
from dotenv import load_dotenv
load_dotenv()
from graphs.dq_agent_graph import build_dq_agent
from src.database import Database
from src.db_inspector import DBInspector
from src.vector_store import SchemaVectorStore
from src.airflow_client import get_airflow_client
from langchain_core.messages import HumanMessage
from langgraph.types import Command

def extract_message_text(message) -> str | None:
    """Return displayable text from a LangChain/Gemini message object.

    Args:
        message: Message object returned by the LangGraph stream.

    Returns:
        str | None: Renderable text content, or `None` when the message has no
        displayable text.

    """
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content or None

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str) and item:
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)

        joined = "\n".join(parts).strip()
        return joined or None

    return None

def handle_interrupt(graph, config) -> bool:
    """Handle a pending graph interrupt for fix approval.

    Args:
        graph: The compiled LangGraph instance.
        config: The graph execution configuration for the current thread.

    Returns:
        bool: True if an interrupt was handled; otherwise, False.

    """
    state = graph.get_state(config)
    if not state.next:
        return False

    # Graph is paused at an interrupt, handle interrupt
    interrupt_data = state.tasks[0].interrupts[0].value
    fix_data = interrupt_data["fix_data"]

    print("\n" + "=" * 60)
    print("⚠️  FIX PROPOSAL")
    print("=" * 60)
    print(f"Table         : {fix_data['table_name']}")
    print(f"Issue         : {fix_data['issue_description']}")
    print(f"Rows affected : {fix_data['rows_affected']}")
    print(f"SQL to execute:\n{fix_data['fix_sql']}")
    print("=" * 60)
    decision = input(f"\n{interrupt_data['question']} ").strip().lower()
    resume_value = "approve" if decision == "approve" else "reject"

    try:
        # Resume the graph
        for chunk in graph.stream(
                Command(resume=resume_value),
                config=config,
                stream_mode="values"
        ):
            last_message = chunk["messages"][-1]
            if getattr(last_message, "type", None) == "ai":
                text = extract_message_text(last_message)
                if text:
                    print(f"\nAgent: {text}\n")
    except Exception as e:
        print(f"Error resuming graph after interrupt: {e}")

    return True

def main():
    """Run the interactive command-line data quality agent session.

    Returns:
        None

    """
    db = Database()
    if not db.test_connection():
        sys.exit(1)

    inspector = DBInspector(db)
    vector_store = SchemaVectorStore(
        api_key=os.environ.get("GEMINI_API_KEY"),
        persist_path="./chroma_db"
    )
    airflow_client = get_airflow_client()

    graph, tools = build_dq_agent(inspector, db, os.environ.get("GEMINI_MODEL"), vector_store, airflow_client)
    thread_id = "dq-session-1"
    config = {"configurable": {"thread_id": thread_id}}

    print("DQ Agent ready. Ask me anything about your data quality.")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input or user_input.lower() == "exit":
                break

            seen_message_ids = set()
            assistant_messages = []
            for chunk in graph.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                    stream_mode="values"
            ):
                last_message = chunk["messages"][-1]

                # Print tool calls as they happen
                if (hasattr(last_message, "tool_calls") and last_message.tool_calls
                        and last_message.id not in seen_message_ids):
                    for tc in last_message.tool_calls:
                        print(f"→ Calling: {tc['name']}({tc['args']})")

                if (getattr(last_message, "type", None) == "ai"
                        and last_message.id not in seen_message_ids):
                    seen_message_ids.add(last_message.id)
                    text = extract_message_text(last_message)
                    if text:
                        assistant_messages.append(text)

            interrupted = handle_interrupt(graph, config)
            if not interrupted and assistant_messages:
                print(f"\nAgent: {assistant_messages[-1]}\n")

    except Exception as e:
        print(f"\nGraph run failed: {e}")
    finally:
        print("\n--- Mermaid Graph ---")
        print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
