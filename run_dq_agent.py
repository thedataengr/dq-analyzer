import sys
from dotenv import load_dotenv
load_dotenv()
from graphs.dq_agent_graph import build_dq_agent
from src.database import Database
from src.db_inspector import DBInspector
from langchain_core.messages import HumanMessage
from langgraph.types import Command


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
            if hasattr(last_message, "content") and last_message.type == "ai" and last_message.content:
                print(f"\nAgent: {last_message.content}\n")
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

    graph, tools = build_dq_agent(inspector, db)
    thread_id = "dq-session-1"
    config = {"configurable": {"thread_id": thread_id}}

    print("DQ Agent ready. Ask me anything about your data quality.")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input or user_input.lower() == "exit":
                break

            final_response = None
            seen_message_ids = set()
            for chunk in graph.stream(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                    stream_mode="values"
            ):
                last_message = chunk["messages"][-1]

                # Print tool calls as they happen
                if (hasattr(last_message, "tool_calls") and last_message.tool_calls
                        and last_message.id not in seen_message_ids):
                    seen_message_ids.add(last_message.id)
                    for tc in last_message.tool_calls:
                        print(f"→ Calling: {tc['name']}({tc['args']})")

                final_response = last_message

            interrupted = handle_interrupt(graph, config)
            if (not interrupted and final_response and hasattr(final_response, "content")
                    and final_response.type == "ai"):
                print(f"\nAgent: {final_response.content}\n")
    except Exception as e:
        print(f"\nGraph run failed: {e}")
    finally:
        print("\n--- Mermaid Graph ---")
        print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
