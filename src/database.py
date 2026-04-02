from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

class Database:
    """Manage SQLAlchemy connectivity and query execution for the app.

    Attributes:
        database_url: Database connection string loaded from the environment.
        engine: SQLAlchemy engine created from the connection string.

    """
    def __init__(self):
        """Load the database URL from the environment and create an engine.

        Returns:
            None

        """
        load_dotenv()
        self.database_url = os.environ.get("DATABASE_URL")
        self.engine = create_engine(self.database_url)


    def test_connection(self) -> bool:
        """Verify that the configured database is reachable.

        Returns:
            bool: True if the connection succeeds; otherwise, False.

        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Could not connect to Database. Connection failed with error: {e}")
            return False


    def run_query(self, sql: str, params: dict = None) -> list:
        """Execute a read query and return rows as dictionaries.

        Args:
            sql: SQL query to execute.
            params: Optional parameter values bound into the query.

        Returns:
            list: Query results represented as dictionaries.

        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            print(f"Query execution failed with error: {e}")
            return []


    def run_write(self, sql: str, params: dict = None):
        """Execute a write statement inside a transaction.

        Args:
            sql: SQL statement to execute.
            params: Optional parameter values bound into the statement.

        Returns:
            None

        """
        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql),params or {})
        except Exception as e:
            print(f"Query execution failed with error: {e}")



