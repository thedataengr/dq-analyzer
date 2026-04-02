import sys, time, os
from dotenv import load_dotenv

from src.database import Database
from src.db_inspector import DBInspector
from src.gemini_client import GeminiClient
from graphs.dq_basic_graph import build_dq_graph
from src.observability import is_tracing_enabled, log_run_metadata

load_dotenv()
from langchain_core.runnables import RunnableConfig

def main():
    """Run a manual data quality graph analysis from the command line.

    Prompts for a table name, executes the graph-based data quality workflow,
    and prints runtime metadata along with the Mermaid graph definition.

    Returns:
        None

    """
    db = Database()
    if db.test_connection():
        print("Database connected successfully")
    else:
        sys.exit(1)

    if is_tracing_enabled():
        print(f"LangSmith tracing: ENABLED (project: {os.environ.get('LANGCHAIN_PROJECT')})")

    inspector = DBInspector(db)
    llm_client = GeminiClient()
    table_name = input("\nWhich table would you like to analyze? ")

    config = RunnableConfig(
        metadata={
            "table_name": table_name,
            "run_type": "manual_analysis"
        },
        tags=["dq-analyzer", "local"]
    )

    graph = build_dq_graph(inspector, llm_client)

    try:
        start = time.time()
        result = graph.invoke({"table_name": table_name}, config=config)
        duration = round(time.time() - start,2)
        print(f"Run completed in {duration}s")

        log_run_metadata(
            table_name=table_name,
            status=result.get("status","unknown"),
            null_pct=result.get("null_pct",0.0),
            duration_s=duration
        )

        if is_tracing_enabled():
            print(f"View trace at: https://smith.langchain.com/projects/dq-analyzer")
    except Exception as e:
        print(f"\nGraph run failed: {e}")
    finally:
        print("\n--- Mermaid Graph ---")
        print(graph.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()

