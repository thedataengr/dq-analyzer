from google.genai import types
from src.db_inspector import DBInspector
from src.tool_registry import ToolRegistry

def build_dq_tools(inspector: DBInspector) -> ToolRegistry:
    """Build Gemini tool declarations and handlers for database inspection.

    Args:
        inspector: Database inspector used by the tool handlers.

    Returns:
        ToolRegistry: Registry containing the Gemini tool declarations and
        callable handlers.

    """
    dq_tool_registry = ToolRegistry()

    get_table_names_tool = types.FunctionDeclaration(
        name="get_table_names",
        description=(
            "Returns all table names in the database to explore schema or prepare for data quality analysis. "
            "Use this as a first step to get list of all available tables before performing any schema exploration "
            "or specific data quality checks on any table."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},  # no parameters
            required=[]
        )
    )


    get_table_schema_tool = types.FunctionDeclaration(
        name="get_table_schema",
        description=(
            "Returns list of column dicts with name and data type of each column in the specified table. "
            "Use this before profiling a table to understand its structure."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "table_name": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The name of the table whose schema needs to be fetched. "
                        "Use exact casing as found in the database."
                    )
                )
            },
            required=["table_name"]
        )
    )


    get_row_count_tool = types.FunctionDeclaration(
        name="get_row_count",
        description=(
            "Returns the total number of rows in a specified table. "
            "Use this to fetch the row count of a table when you need to use row count "
            "to get the table volume or use in any calculation like Null Percentage."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "table_name": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The name of the table for which row count needs to be fetched. "
                        "Use exact casing as found in the database."
                    )
                )
            },
            required=["table_name"]
        )
    )


    get_null_counts_tool = types.FunctionDeclaration(
        name="get_null_counts",
        description=(
            "Returns the null count for each column in a database table as a dict of {column_name: null_count}."
            "Use null count alongside row count to calculate null percentage."),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "table_name": types.Schema(
                    type=types.Type.STRING,
                    description=(
                        "The name of the table to check for null values. "
                        "Use exact casing as found in the database."
                    )
                )
            },
            required=["table_name"]
        )
    )

    def safe_run_query(query: str) -> list:
        """Execute a read-only SQL query after enforcing a SELECT-only policy.

        Args:
            query: SQL query to validate and execute.

        Returns:
            list: Query results, or an error payload when the query is not a
            `SELECT` statement.

        """
        if not query.strip().upper().startswith("SELECT"):
            return [{"error": "Only SELECT queries are allowed"}]
        return inspector.db.run_query(query)

    run_sql_query_tool = types.FunctionDeclaration(
        name="safe_run_query",
        description=(
            "Use to run a read-only SQL query for investigating specific issues. It returns results as list of dicts." 
            "You MUST fetch the table schema first to ensure column names are correct. "
            "Always include a LIMIT clause to prevent excessive data retrieval."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="The complete, valid PostgreSQL SELECT statement to execute."
                )
            },
            required=["query"]
        )
    )

    dq_tool_registry.register(inspector.get_table_names, get_table_names_tool)
    dq_tool_registry.register(inspector.get_table_schema, get_table_schema_tool)
    dq_tool_registry.register(inspector.get_row_count, get_row_count_tool)
    dq_tool_registry.register(inspector.get_null_counts, get_null_counts_tool)
    dq_tool_registry.register(safe_run_query, run_sql_query_tool)

    return dq_tool_registry



