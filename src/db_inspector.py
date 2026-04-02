from sqlalchemy import inspect
from langsmith import traceable
from src.database import Database

class DBInspector:
    """Expose cached schema and profiling helpers for the connected database.

    Attributes:
        db: Database client used to execute SQL queries.
        inspector: SQLAlchemy inspector bound to the engine.

    """
    def __init__(self, database: Database):
        """Initialize SQLAlchemy inspection helpers and in-memory caches.

        Args:
            database: Database client used for query execution.

        """
        self.db = database
        self.inspector = inspect(self.db.engine)
        self._table_names = None    # lazy caching
        self._table_schema = {}
        self._null_counts = {}

    def get_table_names(self) -> list[str]:
        """Return all table names, caching the result after the first lookup.

        Returns:
            list[str]: All discovered table names.

        """
        if self._table_names is None:
            self._table_names = self.inspector.get_table_names()
        return self._table_names

    def _validate_table(self, table_name: str):
        """Validate that a requested table exists in the database.

        Args:
            table_name: Table name to validate.

        Returns:
            None

        """
        known_tables = self.get_table_names()
        if table_name not in known_tables:
            raise ValueError(f"Unknown table: {table_name}")

    @traceable(name="get_table_schema", tags=["database"])
    def get_table_schema(self, table_name: str) -> list[dict]:
        """Return column names and data types for the given table.

        Args:
            table_name: Name of the table to inspect.

        Returns:
            list[dict]: Column metadata for the table.

        """
        self._validate_table(table_name)
        if table_name not in self._table_schema:
            columns = self.inspector.get_columns(table_name)
            self._table_schema[table_name] = [dict(zip(("column_name","data_type"), (col["name"], col["type"])))
                                              for col in columns]
        return self._table_schema[table_name]

    @traceable(name="get_row_count", tags=["database"])
    def get_row_count(self, table_name: str) -> int:
        """Return the number of rows currently stored in the table.

        Args:
            table_name: Name of the table to count.

        Returns:
            int: Number of rows in the table.

        """
        self._validate_table(table_name)
        query = f"SELECT COUNT(*) AS cnt FROM {table_name}"
        result = self.db.run_query(query)
        return result[0]["cnt"] if result else 0

    @traceable(name="get_column_count", tags=["database"])
    def get_column_count(self, table_name: str) -> int:
        """Return the number of columns defined on the table.

        Args:
            table_name: Name of the table to inspect.

        Returns:
            int: Number of columns defined on the table.

        """
        self._validate_table(table_name)
        return len(self.inspector.get_columns(table_name))

    @traceable(name="get_null_counts", tags=["database"])
    def get_null_counts(self, table_name: str) -> dict:
        """Return null counts for every column in the given table.

        Args:
            table_name: Name of the table to analyze.

        Returns:
            dict: Mapping of column names to null counts.

        """
        self._validate_table(table_name)
        if table_name not in self._null_counts:
            # Column names sourced from inspector, not user input — safe here
            # Do not use this pattern with any externally supplied column names
            columns = self.inspector.get_columns(table_name)
            query = "SELECT "
            for col in columns:
                query += f"COUNT(*) - COUNT({col['name']}) AS {col['name']},"
            query = query.rstrip(",") + " FROM " + table_name
            result = self.db.run_query(query)
            self._null_counts[table_name] = result[0]
        return self._null_counts[table_name]
