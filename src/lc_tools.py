from langchain_core.tools import tool
from src.database import Database
from src.db_inspector import DBInspector
from src.dq_checker import DQChecker
import json

def build_lc_tools(inspector: DBInspector, db: Database,
                   vector_store=None, airflow_client=None) -> list:
    """Build LangChain tool wrappers for database inspection and fixes.

    Args:
        inspector: Database inspector used by the tool implementations.
        db: Database client used to execute SQL queries and writes.
        vector_store: Optional SchemaVectorStore for RAG-based schema search.
        airflow_client: Optional Airflow client for pipeline monitoring tools.

    Returns:
        list: LangChain tool callables exposed to the agent.

    """
    @tool
    def get_table_names() -> list[str]:
        """Get all table names in the database.

        Call this first to discover available tables before any analysis.
        This will return a complete list of all available tables.

        Returns:
            list[str]: Names of all available tables.

        """
        return inspector.get_table_names()

    @tool
    def get_table_schema(table_name: str) -> list[dict]:
        """Get the schema of a table, including column names and data types.

        Call this before profiling to understand the table structure.

        Args:
            table_name: Exact table name as found in the database.

        Returns:
            list[dict]: Column metadata for the table.

        """
        return inspector.get_table_schema(table_name)

    @tool
    def get_row_count(table_name: str) -> int:
        """Get the total number of rows in a table.

        Use this to fetch the row count for calculations such as null
        percentage.

        Args:
            table_name: Exact table name as found in the database.

        Returns:
            int: Number of rows in the table.

        """
        return inspector.get_row_count(table_name)

    @tool
    def get_null_counts(table_name: str) -> dict:
        """Return the null count for each column in a database table.

        Use null counts alongside row counts to calculate null percentage.

        Args:
            table_name: Exact table name as found in the database.

        Returns:
            dict: Mapping of column names to null counts.

        """
        return inspector.get_null_counts(table_name)

    @tool
    def run_sql_query(query: str) -> list[dict]:
        """Run a read-only SQL query for investigating specific issues.

        Fetch the table schema first to ensure column names are correct.
        Always include a `LIMIT` clause to prevent excessive data retrieval.

        Args:
            query: The complete, valid PostgreSQL SELECT statement to execute.

        Returns:
            list[dict]: Query results, or an error payload when the query is not
            a `SELECT` statement.

        """
        if not query.strip().upper().startswith("SELECT"):
            return [{"error": "Only SELECT queries are allowed"}]
        return db.run_query(query)

    @tool
    def propose_fix(
            table_name: str,
            issue_description: str,
            fix_sql: str,
            rows_affected: int
    ) -> str:
        """Propose a data quality fix for human review.

        Always use this tool when you want to fix an issue. Never execute fixes
        directly. The human reviewer will approve or reject the proposal. Do not
        call this tool simultaneously with other tools.

        Args:
            table_name: Table the fix applies to.
            issue_description: Plain English description of the issue being fixed.
            fix_sql: The exact SQL UPDATE/DELETE statement to execute if approved.
            rows_affected: Estimated number of rows that will be modified.

        Returns:
            str: JSON-encoded fix proposal payload.

        """
        return json.dumps({
            "table_name": table_name,
            "issue_description": issue_description,
            "fix_sql": fix_sql,
            "rows_affected": rows_affected
        })

    @tool
    def get_duplicate_count(table_name: str, column_name: str) -> dict:
        """Get the count of duplicate values in a specific column.

        Use this before proposing deduplication fixes.

        Args:
            table_name: Table to check for duplicates.
            column_name: Column to check for duplicate values.

        Returns:
            dict: Duplicate rows grouped by value, or an error payload when the
            table or column is invalid.

        """
        # Validate against known tables and columns
        known_tables = inspector.get_table_names()
        if table_name not in known_tables:
            return {"error": f"Unknown table: {table_name}"}

        known_columns = [col["column_name"] for col in inspector.get_table_schema(table_name)]
        if column_name not in known_columns:
            return {"error": f"Unknown column: {column_name}"}

        query = f"""
            SELECT {column_name}, COUNT(*) as count 
            FROM {table_name} 
            GROUP BY {column_name} 
            HAVING COUNT(*) > 1
            LIMIT 20
        """
        return {"duplicates": db.run_query(query)}

    @tool
    def run_dq_checks(table_name: str) -> dict:
        """Run predefined data quality checks on a table.

        This returns structured pass/fail results for each check with affected
        row counts. Use this to get deterministic rule-based validation after
        null analysis. Call `get_table_names` first to verify that the table
        exists.

        Args:
            table_name: Table to run quality checks against.

        Returns:
            dict: Structured validation results for the table.

        """
        checker = DQChecker(db.database_url)
        return checker.run_checks(table_name)

    @tool
    def search_schema_docs(query: str) -> list[dict]:
        """Search schema documentation for business context about tables and columns.

        Use this when the question is about semantic meaning rather than raw data.
        This is the right tool for questions about business definitions, expected
        behavior, known historical issues, ETL timing, validation rules, and
        root-cause clues already documented by humans. Prefer this over SQL when
        you need explanatory context such as "what does this column mean?" or
        "why might this table contain nulls?" Do not use it to count rows,
        inspect live values, or validate current database contents.

        Args:
            query: Natural language question about a table, column, pipeline, or
                known issue described in the schema documentation.

        Returns:
            list[dict]: Top matching documentation chunks returned by the vector
            search backend.

        """
        return vector_store.search(query, n_results=2)

    @tool
    def get_dag_list():
        """List available Airflow DAGs and whether each one is paused.

        Use this first when the user refers to pipelines, jobs, schedulers, or
        Airflow without naming a specific DAG. This helps discover the relevant
        DAG ID before calling more specific Airflow tools. Do not use this when
        you already know the DAG ID and need run-level details.

        Returns:
            list[dict]: DAG metadata including `dag_id`, pause status, and last
            parsed time when available.

        """

        return airflow_client.get_dags()

    @tool
    def get_dag_status(dag_id: str):
        """Get the latest status for a specific Airflow DAG.

        Use this when you already know the DAG ID and need a quick health check:
        whether the DAG is paused, what its latest run state is, and when that
        run started or ended. Prefer this over run history when the question is
        simply "is the pipeline failing?" or "what is its current status?"

        Args:
            dag_id: Exact Airflow DAG ID to inspect.

        Returns:
            dict: Latest DAG status including DAG metadata and the most recent
            run information.

        """

        return airflow_client.get_dag_status(dag_id)

    @tool
    def get_dag_run_history(dag_id: str, limit: int = 5):
        """Get recent run history for a specific Airflow DAG.

        Use this when you need trend information across multiple runs, such as
        checking whether failures are intermittent, recent, or recurring.
        Prefer this over `get_dag_status` when one latest run is not enough to
        diagnose reliability. If a failed run appears relevant, follow up with
        `get_failed_task_logs` using its `run_id`.

        Args:
            dag_id: Exact Airflow DAG ID to inspect.
            limit: Maximum number of recent DAG runs to return.

        Returns:
            list[dict]: Recent DAG runs with normalized state and timing fields.

        """

        return airflow_client.get_dag_run_history(dag_id, limit)

    @tool
    def get_failed_task_logs(dag_id: str, run_id: str):
        """Get failed-task details for a specific DAG run.

        Use this only after identifying a failed run from `get_dag_status` or
        `get_dag_run_history`. This is the right tool when the user asks why a
        pipeline failed, which task failed, or what the underlying error was.
        Do not call it for successful or still-running runs because it is
        focused on failure diagnosis.

        Args:
            dag_id: Exact Airflow DAG ID that owns the run.
            run_id: Exact DAG run identifier for the failed run to inspect.

        Returns:
            list[dict]: Failed task entries including task ID, state, and log
            content or an error message from log retrieval.

        """

        return airflow_client.get_failed_task_logs(dag_id, run_id)

    tools = [get_table_names, get_table_schema, get_row_count,
            get_null_counts, run_sql_query, propose_fix, get_duplicate_count, run_dq_checks]

    if vector_store:
        tools.append(search_schema_docs)

    if airflow_client:
        tools += [get_dag_list, get_dag_status, get_dag_run_history, get_failed_task_logs]

    return tools
