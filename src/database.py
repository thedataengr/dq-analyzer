from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

class Database:
    def __init__(self):
        load_dotenv()
        self.database_url = os.environ.get("DATABASE_URL")
        self.engine = create_engine(self.database_url)

    def test_connection(self) -> bool:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Could not connect to Database. Connection failed with error: {e}")
            return False

    def run_query(self, sql: str, params: dict = None) -> list:
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql), params or {})
                columns = result.keys()
                return [dict(zip(columns, row)) for row in result.fetchall()]
                # return [r._mapping for r in result]
        except Exception as e:
            print(f"Query execution failed with error: {e}")
            return []


    def run_write(self, sql: str, params: dict = None):
        try:
            with self.engine.begin() as conn:
                conn.execute(text(sql),params or {})
        except Exception as e:
            print(f"Query execution failed with error: {e}")



