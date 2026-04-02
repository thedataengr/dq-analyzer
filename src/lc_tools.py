from langchain_core.tools import tool
from src.database import Database
from src.db_inspector import DBInspector
from src.dq_checker import DQChecker
import json

def build_lc_tools(inspector: DBInspector, db: Database) -> list:
    """Build LangChain tool wrappers for database inspection and fixes.

    Args:
        inspector: Database inspector used by the tool implementations.
        db: Database client used to execute SQL queries and writes.

    Returns:
        list: LangChain tool callables exposed to the agent.

    """
    @tool
    def get_table_names() -> list[str]:
        """Get all table names in the database.

        Call this first to discover available tables before any analysis.

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

    return [get_table_names, get_table_schema, get_row_count,
            get_null_counts, run_sql_query, propose_fix, get_duplicate_count, run_dq_checks]
