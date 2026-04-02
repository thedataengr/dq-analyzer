from src.database import Database
from src.db_inspector import DBInspector
from src.dq_tools import build_dq_tools
from src.tool_agent import DQToolAgent
from src.gemini_client import GeminiClient

if __name__ == "__main__":
    db = Database()

    inspector = DBInspector(db)
    registry = build_dq_tools(inspector)
    gemini_client = GeminiClient(model="gemini-2.5-flash-lite")  # model="gemini-2.5-flash-lite"
    agent = DQToolAgent(gemini_client,registry)
    prompt = (
        "Investigate the data quality of all tables in the database. "
        "For each table, check the null counts and tell me which tables "
        "and columns need the most urgent attention."
    )
    print("Starting DQ Tool Agent...")
    print(f"User: {prompt}")
    agent_response = agent.run(prompt)
    print("\nAgent Response:")
    print(agent_response)



