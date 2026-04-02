from langgraph.graph import StateGraph, END
from typing import TypedDict
from src.db_inspector import DBInspector

class DQState(TypedDict):
    """Represents the state carried through the DQ analysis graph.

    Attributes:
        table_name: Name of the table being analyzed.
        schema: Schema metadata returned by `DBInspector`.
        row_count: Number of rows in the table.
        null_counts: Null count per column.
        null_pct: Overall null percentage across the table.
        status: Severity classification for the table.
        analysis_result: Structured LLM analysis output.
        needs_escalation: Whether the table requires escalation.
        needs_llm_analysis: Whether the table requires LLM analysis.

    """
    table_name: str
    schema: list           # from DBInspector
    row_count: int         # from DBInspector
    null_counts: dict      # from DBInspector
    null_pct: float        # calculated
    status: str            # critical/warning/ok
    analysis_result: dict          # from LLM
    needs_escalation: bool
    needs_llm_analysis: bool


def build_dq_graph(inspector: DBInspector, llm_client):
    """Build the data quality analysis graph.

    Args:
        inspector: Database inspector used to fetch schema and table statistics.
        llm_client: Client used for optional LLM-based table analysis.

    Returns:
        CompiledStateGraph: The compiled LangGraph workflow for table analysis.

    """

    def fetch_schema(state: DQState) -> dict:
        """Fetch the schema for the target table.

        Retrieves column names and data types for the table being analyzed.
        The schema is stored in graph state for later validation and reporting.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            dict: A state update containing the table schema.

        """
        print(f"\n[fetch_schema] Fetching schema for {state['table_name']}...")
        schema = inspector.get_table_schema(state["table_name"])
        return {"schema": schema}

    def fetch_stats(state: DQState) -> dict:
        """Fetch table statistics and compute the overall null percentage.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            dict: A state update containing the row count, per-column null
            counts, and overall null percentage.

        """
        row_count = inspector.get_row_count(state["table_name"])
        null_counts = inspector.get_null_counts(state["table_name"])
        total_null_count = sum(null_counts.values())
        column_count = inspector.get_column_count(state["table_name"])
        null_pct = round(total_null_count/(row_count*column_count)*100,2) if row_count > 0 else 0.0
        result = f"""[fetch_stats] Fetching statistics for {state["table_name"]}...
  → Row count: {row_count}
  → Total nulls: {total_null_count}
  → Null %: {null_pct}
"""
        return {
            "row_count": row_count,
            "null_counts": null_counts,
            "null_pct": null_pct
        }

    def classify_severity(state: DQState) -> dict:
        """Classify table severity from the computed null percentage.

        Thresholds:
            Critical: Greater than 10 percent null values.
            Warning: Greater than 5 percent null values.
            OK: 5 percent null values or fewer.

        Args:
            state: The current state of the DQ pipeline containing `null_pct`.

        Returns:
            dict: A state update containing the severity classification, routing
            flags, and an empty analysis result placeholder.

        """
        if state["null_pct"] > 10:
            status = "critical"
        elif state["null_pct"] > 5:
            status = "warning"
        else:
            status = "ok"
        needs_escalation = status == "critical"
        needs_llm_analysis = status in ("critical","warning")
        print(f"\n[classify_severity] Status: {status}")
        return {
            "status": status,
            "needs_escalation": needs_escalation,
            "needs_llm_analysis": needs_llm_analysis,
            "analysis_result": {},
        }


    def analyse_with_llm(state: DQState) -> dict:
        """Request LLM analysis for tables that need deeper inspection.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            dict: A state update containing the structured LLM analysis result.

        """
        if llm_client.is_available():
            print("\n[analyse_with_llm] Calling LLM for analysis...")
            response = llm_client.analyse_table(state["table_name"],state["null_counts"], state["row_count"])
            if response:
                analysis_result = response
                print("→ Analysis complete")
            else:
                analysis_result = {}
                print("\n[analyse_with_llm] LLM returned no analysis")
        else:
            print("\n[analyse_with_llm] LLM is not available to analyse this table")
            analysis_result = {}
        return {
            "analysis_result": analysis_result
        }

    def escalate(state: DQState) -> dict:
        """Emit a console alert for tables classified as critical.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            dict: An empty state update after logging the alert.

        """
        alert_msg = f"""\n[escalate]🚨 ESCALATION ALERT
  Table: {state["table_name"]}
  Status: CRITICAL ({state["null_pct"]}% nulls)
  Immediate attention required.
"""
        print(alert_msg)
        return {}

    def log_result(state: DQState) -> dict:
        """Print the final analysis result for the current table.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            dict: An empty state update after printing the result.

        """
        result = f"""\n[log_result] ✓ Analysis complete for {state["table_name"]}
  Status    : {state["status"]}
  Null %    : {state["null_pct"]}
  Analysis  : {state["analysis_result"].get("summary", "")}
  Action    : {state["analysis_result"].get("top_recommendation", "")}
"""
        print(result)
        return {}

    def route_by_severity(state: DQState) -> str:
        """Choose the next node based on whether LLM analysis is needed.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            str: `"analyse_with_llm"` when deeper analysis is required;
            otherwise `"log_result"`.

        """
        if state["needs_llm_analysis"]:
            return "analyse_with_llm"
        return "log_result"

    def route_after_llm(state: DQState) -> str:
        """Choose the next node after the LLM analysis step.

        Args:
            state: The current state of the DQ pipeline.

        Returns:
            str: `"escalate"` for critical tables; otherwise `"log_result"`.

        """
        if state["status"] == "critical":
            return "escalate"
        return "log_result"

    # Build and return the compiled graph
    workflow = StateGraph(DQState)
    workflow.add_node("fetch_schema", fetch_schema)
    workflow.add_node("fetch_stats", fetch_stats)
    workflow.add_node("classify_severity", classify_severity)
    workflow.add_node("analyse_with_llm", analyse_with_llm)
    workflow.add_node("escalate", escalate)
    workflow.add_node("log_result", log_result)

    workflow.set_entry_point("fetch_schema")
    workflow.add_edge("fetch_schema", "fetch_stats")
    workflow.add_edge("fetch_stats", "classify_severity")

    workflow.add_conditional_edges(
        "classify_severity",  # from this node
        route_by_severity,  # call this function to decide
        {  # map return values to node names
            "analyse_with_llm": "analyse_with_llm",
            "log_result": "log_result",
        }
    )
    workflow.add_conditional_edges(
        "analyse_with_llm",
        route_after_llm,
        {
            "escalate": "escalate",
            "log_result": "log_result"
        }
    )
    workflow.add_edge("escalate", "log_result")
    workflow.add_edge("log_result", END)

    return workflow.compile()


