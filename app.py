import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from src.database import Database
from src.db_inspector import DBInspector
from graphs.dq_agent_graph import build_dq_agent

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

def init_session_state():
    """Initialize the Streamlit session keys used by the UI.

    Returns:
        None

    """
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "session-1"
    if "fix_history" not in st.session_state:
        st.session_state.fix_history = []
    if "current_model" not in st.session_state:
        st.session_state.current_model = "gemini-2.5-flash"
    if "pending_interrupt" not in st.session_state:
        st.session_state.pending_interrupt = None
    if "session_count" not in st.session_state:
        st.session_state.session_count = 1

@st.cache_resource
def init_agent(ai_model):
    """Create and cache the graph-backed agent for the selected model.

    Args:
        ai_model: The Gemini model name selected in the UI.

    Returns:
        tuple: A tuple of `(db, inspector, graph)` when initialization succeeds,
        or `(None, None, None)` if the database connection fails.

    """
    load_dotenv()
    db = Database()
    if not db.test_connection():
        return None, None, None
    inspector = DBInspector(db)
    graph, tools = build_dq_agent(inspector, db, ai_model)
    return db, inspector, graph

def resume_graph(graph, config, resume_value):
    """Resume the graph after a fix approval or rejection decision.

    Args:
        graph: The compiled LangGraph instance.
        config: The graph execution configuration for the current session.
        resume_value: The decision used to resume the interrupt, typically
            `"approve"` or `"reject"`.

    Returns:
        None

    """
    assistant_messages = []
    seen_message_ids = set()
    try:
        status_label = "Applying Fix..." if resume_value == "approve" else "Rejecting Fix..."
        with st.status(status_label) as status:
            for chunk in graph.stream(
                    Command(resume=resume_value),
                    config=config,
                    stream_mode="values"
            ):
                last_message = chunk["messages"][-1]
                message_id = getattr(last_message, "id", None)
                if (
                    getattr(last_message, "type", None) == "ai"
                    and message_id not in seen_message_ids
                ):
                    seen_message_ids.add(message_id)
                    text = extract_message_text(last_message)
                    if text:
                        assistant_messages.append(text)

            status.update(label="Action Complete!", state="complete", expanded=False)

        for text in assistant_messages:
            st.session_state.messages.append({"role": "assistant", "content": text})
    except Exception as e:
        error_message = f"Error resuming graph after interrupt: {e}"
        st.error(error_message)
        st.session_state.messages.append({"role": "assistant", "content": error_message})

    st.session_state.pending_interrupt = None

def main():
    """Render the Streamlit app and handle chat and report interactions.

    Returns:
        None

    """
    # Page config
    st.set_page_config(page_title="DQ Analyzer", page_icon="🔍", layout="wide")

    init_session_state()

    with st.sidebar:
        st.title("Data Quality Analyzer")
        st.divider()

        selected_model = st.selectbox("AI Model",
                             ["gemini-2.5-flash", "gemini-3.1-flash-lite-preview"],
                             help="Flash is faster; Flash-Lite is more cost-efficient.")

    db, inspector, graph = init_agent(selected_model)
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    if st.session_state.current_model != selected_model:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"🔄 Model switched to **{selected_model}**."
        })
        st.session_state.current_model = selected_model

    with st.sidebar:
        if graph:
            st.success("● Database Connected")
        else:
            st.error("○ Database Not Connected")
            return

        if st.button("New Session", type="secondary", use_container_width=True):
            st.session_state.session_count += 1
            st.session_state.thread_id = f"session-{st.session_state.session_count}"
            st.session_state.messages = []
            st.session_state.fix_history = []
            st.session_state.pending_interrupt = None
            st.rerun()

        st.divider()
        # Display fix history
        with st.expander(f"📜 Fix History ({len(st.session_state.fix_history)})"):
            if not st.session_state.fix_history:
                st.info("No fixes attempted yet.")
            else:
                for i, fix in enumerate(st.session_state.fix_history):
                    st.markdown(f"**{i + 1}. {fix['table_name']}**")
                    st.markdown(f"**Issue:** {fix['issue_description']}")
                    st.markdown(f"**Rows Affected:** {fix['rows_affected']}")
                    st.caption(f"Status: {fix['status']}")
                    if st.button("View SQL", key=f"btn_{i}"):
                        st.code(fix['fix_sql'], language="sql")

    # tabs
    chat_tab, dqr_tab = st.tabs(["Chat", "DQ Report"])

    with chat_tab:
        st.header("Chat with DQ Agent")

        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        if st.session_state.get("pending_interrupt"):
            interrupt_data = st.session_state.pending_interrupt
            fix_data = interrupt_data["fix_data"]

            # Show fix proposal
            st.warning("⚠️ Fix Proposal Requires Approval")

            with st.container(border=True):
                st.write(f"**Table:** {fix_data['table_name']}")
                st.write(f"**Issue:** {fix_data['issue_description']}")
                st.write(f"**Rows affected:** {fix_data['rows_affected']}")
                st.code(fix_data['fix_sql'], language="sql")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Fix", type="primary", use_container_width=True):
                    st.session_state.fix_history.append({
                        "table_name": fix_data['table_name'],
                        "issue_description": fix_data['issue_description'],
                        "rows_affected": fix_data['rows_affected'],
                        "fix_sql": fix_data['fix_sql'],
                        "status": "Applied"
                    })
                    resume_graph(graph, config, "approve")
                    st.rerun()
            with col2:
                if st.button("❌ Reject Fix", use_container_width=True):
                    st.session_state.fix_history.append({
                        "table_name": fix_data['table_name'],
                        "issue_description": fix_data['issue_description'],
                        "rows_affected": fix_data['rows_affected'],
                        "fix_sql": fix_data['fix_sql'],
                        "status": "Rejected"
                    })
                    resume_graph(graph, config, "reject")
                    st.rerun()

        # Chat input — blocks until user submits
        if prompt := st.chat_input("Ask about your data quality..."):
            # Add user message to history
            st.session_state.messages.append({"role": "user", "content": prompt})

            with chat_container:
                # Display user message
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Generate and display agent response
                with st.chat_message("assistant"):
                    tool_calls_made = []
                    assistant_messages = []
                    seen_message_ids = set()

                    try:
                        with st.status("Analyzing data...", expanded=True) as status:
                            for chunk in graph.stream(
                                {"messages": [HumanMessage(content=prompt)]},
                                config=config,
                                stream_mode="values"
                            ):
                                last_message = chunk["messages"][-1]
                                message_id = getattr(last_message, "id", None)

                                if (
                                    hasattr(last_message, "tool_calls")
                                    and last_message.tool_calls
                                    and message_id not in seen_message_ids
                                ):
                                    for tc in last_message.tool_calls:
                                        tool_calls_made.append(tc)

                                if (
                                    getattr(last_message, "type", None) == "ai"
                                    and message_id not in seen_message_ids
                                ):
                                    seen_message_ids.add(message_id)
                                    text = extract_message_text(last_message)
                                    if text:
                                        assistant_messages.append(text)

                            status.update(label="Analysis Complete!", state="complete", expanded=False)
                    except Exception as e:
                        error_message = f"Graph run failed: {e}"
                        st.error(error_message)
                        st.session_state.messages.append({"role": "assistant", "content": error_message})
                        return

                    # Show tool calls in expander
                    if tool_calls_made:
                        with st.expander(f"🔧 {len(tool_calls_made)} tool calls made"):
                            for tc in tool_calls_made:
                                st.code(f"{tc['name']}({tc['args']})", language="python")

                    for text in assistant_messages:
                        st.markdown(text)
                        st.session_state.messages.append({"role": "assistant", "content": text})

                    # Check for pending interrupt
                    state = graph.get_state(config)
                    if state.next:
                        interrupt_data = state.tasks[0].interrupts[0].value
                        st.session_state.pending_interrupt = interrupt_data
                        st.rerun()

    with dqr_tab:
        st.header("Data Quality Report")

        col1, col2 = st.columns([3, 1], vertical_alignment="center")
        with col1:
            st.markdown("Run a comprehensive suite of checks across all tables")
        with col2:
            run_pressed = st.button("🚀 Run Full Report", type="primary", use_container_width=True)

        if run_pressed:
            from src.dq_checker import DQChecker
            checker = DQChecker(db.database_url)

            with st.status("Running Data Quality Checks...", expanded=True) as status:
                # Execute DQ checks
                dq_reports = checker.run_all_checks(inspector.get_table_names())
                status.update(label="Checks Complete!", state="complete", expanded=False)

            if not dq_reports:
                st.warning("DQ Reports not found or DQ checks failed to run.")
            else:
                # Summary Table Processing
                summary_list = []
                for report in dq_reports:
                    status_icon = "✅ PASS" if report["failed"] == 0 else "❌ FAIL"
                    summary_list.append({
                        "Status": status_icon,
                        "Table": report["table"],
                        "Total": report["total_checks"],
                        "Passed": report["passed"],
                        "Failed": report["failed"]
                    })

                st.subheader("Table-wise Summary")
                st.dataframe(summary_list, use_container_width=True, hide_index=True)

                # Failure details
                st.subheader("Issue Details")
                for report in dq_reports:
                    # Show tables that have failures
                    if report["failed"] > 0:
                        with st.expander(f"🚩 {report['table']} — {report['failed']} issues detected"):
                            # Create a list of failed checks
                            failed_checks = [c for c in report["checks"] if not c["passed"]]

                            # Prepare data for the sub-table
                            failure_details = []
                            for fc in failed_checks:
                                failure_details.append({
                                    "Check Type": fc["check"].replace("expect_column_", "").replace("expect_table_", ""),
                                    "Column": fc.get("column", "Table-Level"),
                                    "Failed Rows": fc.get("failed_rows", "N/A"),
                                    "Failed %": f"{fc.get('failed_pct', 0):.2f}%" if "failed_pct" in fc else "N/A"
                                })

                            st.table(failure_details)
                    else:
                        st.success(f"✔️ {report['table']} passed all checks.")

if __name__ == "__main__":
    main()

# Run with: streamlit run app.py
