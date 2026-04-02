import os
from langsmith import Client
from datetime import datetime, timezone

def get_langsmith_client() -> Client | None:
    """Return a LangSmith client when the required API key is configured.

    Returns:
        Client | None: Configured LangSmith client, or `None` if tracing is not
        configured.

    """
    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        return None
    return Client(api_key=api_key)

def is_tracing_enabled() -> bool:
    """Return whether LangSmith tracing environment variables are configured.

    Returns:
        bool: True if tracing is enabled; otherwise, False.

    """
    return (
        os.environ.get("LANGCHAIN_TRACING_V2") == "true"
        and os.environ.get("LANGCHAIN_API_KEY") is not None
    )

def log_run_metadata(table_name: str, status: str, null_pct: float, duration_s: float):
    """Log structured metadata for a completed data quality run.

    Args:
        table_name: Name of the table that was analyzed.
        status: Computed severity status for the table.
        null_pct: Overall null percentage for the table.
        duration_s: Execution time in seconds.

    Returns:
        None

    """
    metadata = {
        "table": table_name,
        "status": status,
        "null_pct": null_pct,
        "duration_s": duration_s,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    print(f"[observability] Run metadata: {metadata}")  # Future: write to DB, send to monitoring system, etc.

