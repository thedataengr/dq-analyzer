import streamlit as st
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from src.database import Database
from src.db_inspector import DBInspector
from src.vector_store import SchemaVectorStore
from src.airflow_client import get_airflow_client
from graphs.dq_agent_graph import build_dq_agent

# Map tool names to readable labels
TOOL_LABELS = {
    "get_table_names": "📋 Listing tables",
    "get_table_schema": "🔍 Reading schema",
    "get_row_count": "🔢 Counting rows",
    "get_null_counts": "🕳️ Checking nulls",
    "run_sql_query": "⚡ Running query",
    "run_dq_checks": "✅ Running GX checks",
    "search_schema_docs": "📚 Searching docs",
    "get_dag_list": "🔄 Listing pipelines",
    "get_dag_status": "📊 Checking pipeline status",
    "get_dag_run_history": "📈 Fetching run history",
    "get_failed_task_logs": "🔴 Reading failure logs",
    "propose_fix": "🔧 Proposing fix",
}

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
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    if "session_count" not in st.session_state:
        st.session_state.session_count = 1
    if "pipeline_status" not in st.session_state:
        st.session_state.pipeline_status = None


@st.cache_resource
def init_agent(ai_model):
    """Create and cache the graph-backed agent for the selected model.

    Args:
        ai_model: The Gemini model name selected in the UI.

    Returns:
        tuple: A tuple of `(db, inspector, graph, vector_store, airflow_client)` when initialization succeeds,
        or `(None, None, None, None, None)` if the database connection fails.

    """
    load_dotenv()
    db = Database()
    if not db.test_connection():
        return None, None, None, None, None
    inspector = DBInspector(db)
    vector_store = SchemaVectorStore(
        api_key=os.environ.get("GEMINI_API_KEY"),
        persist_path="./chroma_db"
    )
    airflow_client = get_airflow_client()

    graph, tools = build_dq_agent(inspector, db, ai_model, vector_store, airflow_client)

    return db, inspector, graph, vector_store, airflow_client

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

                if (
                    getattr(last_message, "type", None) == "ai"
                    and last_message.id not in seen_message_ids
                ):
                    seen_message_ids.add(last_message.id)
                    text = extract_message_text(last_message)
                    if text:
                        assistant_messages.append(text)

            status.update(label="Action Complete!", state="complete", expanded=False)

        for text in assistant_messages:
            st.session_state.messages.append({"role": "assistant", "content": text})

    except Exception as e:
        error_text = str(e)
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            error_message = "Quota exceeded for this model. Please select another model or try again later."
        elif "503" in error_text or "UNAVAILABLE" in error_text:
            error_message = "This model is currently unavailable. Please select another model or try again later."
        else:
            error_message = f"Error while resuming after interrupt: {e}"
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
                             ["gemini-2.5-flash", "gemini-2.5-flash-lite",
                                    "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview",
                                    "gemma-4-31b-it", "gemma-4-26b-a4b-it"],
                             help="Flash models are faster; Flash-Lite models are cost-efficient.")

    db, inspector, graph, vector_store, airflow_client = init_agent(selected_model)
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
            st.session_state.pending_prompt = None
            st.session_state.pipeline_status = None
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

        st.divider()
        st.caption("Knowledge Base")
        if vector_store and vector_store.is_indexed():
            stats = vector_store.get_collection_stats()
            st.success(f"● Schema docs indexed ({stats['total_documents']} tables)")
        else:
            st.warning("○ Schema docs not indexed")
            if st.button("Index Schema Docs"):
                with st.spinner("Indexing..."):
                    vector_store.index_documents("./docs/schema_docs.md")
                st.rerun()

    # tabs
    chat_tab, dqr_tab, pipeline_tab = st.tabs(["Chat", "DQ Report", "Pipeline Status"])

    with chat_tab:
        st.header("Chat with DQ Agent")

        # Display chat history
        chat_container = st.container()
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    # Show tool calls in expander
                    tool_calls_made = message.get("tool_calls", [])
                    if tool_calls_made:
                        # Filter out 'propose_fix' tool call as it has its own UI
                        display_calls = [tc for tc in tool_calls_made if tc['name'] != 'propose_fix']
                        if display_calls:
                            with st.expander(f"🔧 {len(display_calls)} tool calls"):
                                for tc in display_calls:
                                    label = TOOL_LABELS.get(tc['name'], tc['name'])
                                    st.markdown(f"**{label}**")
                                    if tc['args']:
                                        st.json(tc['args'])

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
        prompt = st.session_state.pop("pending_prompt", None)
        if prompt is None and st.session_state.pending_interrupt is None:
            prompt = st.chat_input("Ask about your data quality...")

        # Example prompts
        if not (st.session_state.messages or prompt):
            st.markdown("**Try asking:**")
            examples = [
                "Why does the orders table have null customer IDs?",
                "Is the null customer_id issue related to an ETL failure?",
                "Run the full quality checks on all tables",
                "What pipelines are failing and why?",
            ]
            cols = st.columns(2)
            for i, example in enumerate(examples):
                with cols[i % 2]:
                    if st.button(example, use_container_width=True):
                        st.session_state.pending_prompt = example
                        st.rerun()

        if prompt:
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

                                if (
                                    hasattr(last_message, "tool_calls")
                                    and last_message.tool_calls
                                    and last_message.id not in seen_message_ids
                                ):
                                    for tc in last_message.tool_calls:
                                        tool_calls_made.append(tc)

                                if (
                                    getattr(last_message, "type", None) == "ai"
                                    and last_message.id not in seen_message_ids
                                ):
                                    seen_message_ids.add(last_message.id)
                                    text = extract_message_text(last_message)
                                    if text:
                                        assistant_messages.append(text)

                            status.update(label="Analysis Complete!", state="complete", expanded=False)

                    except Exception as e:
                        error_text = str(e)
                        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                            error_message = "Quota exceeded for this model. Please select another model or try again later."
                        elif "503" in error_text or "UNAVAILABLE" in error_text:
                            error_message = "This model is currently unavailable. Please select another model or try again later."
                        else:
                            error_message = f"Error: {e}"
                        st.error(error_message)
                        st.session_state.messages.append({"role": "assistant", "content": error_message})
                        return

                    if assistant_messages:
                        st.markdown(assistant_messages[-1])

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": assistant_messages[-1],
                            "tool_calls": tool_calls_made
                        })

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
                st.dataframe(summary_list, width='stretch', hide_index=True)

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


    with pipeline_tab:
        st.header("Airflow Pipeline Status")

        if st.button("🔄 Refresh Pipeline Status", type="primary"):
            dags = airflow_client.get_dags()
            # Fetch status for each DAG at refresh time, not on every rerun
            st.session_state.pipeline_status = [
                {**dag, "status": airflow_client.get_dag_status(dag["dag_id"])}
                for dag in dags
            ]

        if st.session_state.get("pipeline_status"):
            for dag in st.session_state.pipeline_status:
                dag_id = dag["dag_id"]
                status = dag["status"]
                state = status.get("state", "unknown")
                is_paused = dag.get("is_paused", False)

                # Colour code by state
                if is_paused:
                    st.warning(f"⏸️ {dag_id} — Paused")
                elif state == "success":
                    st.success(f"✅ {dag_id} — Last run successful")
                elif state == "failed":
                    st.error(f"❌ {dag_id} — Last run FAILED")

                    # Show failure details in expander
                    with st.expander("View failure details"):
                        run_id = status.get("run_id")
                        if run_id:
                            logs = airflow_client.get_failed_task_logs(dag_id, run_id)
                            for log in logs:
                                st.markdown(f"**Task:** {log['task_id']}")
                                st.code(log['log'], language="text")
                else:
                    st.info(f"ℹ️ {dag_id} — {state}")

if __name__ == "__main__":
    main()

# Run with: streamlit run app.py
