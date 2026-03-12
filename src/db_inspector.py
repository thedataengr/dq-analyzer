from sqlalchemy import inspect
from src.database import Database

class DBInspector:
    def __init__(self, database: Database):
        self.db = database
        self.inspector = inspect(self.db.engine)
        self._table_names = None    # lazy caching
        self._table_schema = {}
        self._null_counts = {}

    def get_table_names(self) -> list[str]:
        if self._table_names is None:
            self._table_names = self.inspector.get_table_names()
        return self._table_names

    def _validate_table(self, table_name: str):
        known_tables = self.get_table_names()
        if table_name not in known_tables:
            raise ValueError(f"Unknown table: {table_name}")

    def get_table_schema(self, table_name: str) -> list[dict]:
        self._validate_table(table_name)
        if table_name not in self._table_schema:
            columns = self.inspector.get_columns(table_name)
            self._table_schema[table_name] = [dict(zip(("column_name","data_type"), (col["name"], col["type"])))
                                              for col in columns]
        return self._table_schema[table_name]

    def get_row_count(self, table_name: str) -> int:
        self._validate_table(table_name)
        query = f"SELECT COUNT(*) AS cnt FROM {table_name}"
        result = self.db.run_query(query)
        return result[0]["cnt"] if result else 0

    def get_column_count(self, table_name: str) -> int:
        self._validate_table(table_name)
        return len(self.inspector.get_columns(table_name))

    def get_null_counts(self, table_name: str) -> dict:
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
