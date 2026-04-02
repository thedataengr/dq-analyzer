import sys
import time
import asyncio

from src.database import Database
from src.db_inspector import DBInspector
from src.reporter import DQReporter
from src.llm_client import LLMClient
from src.chat_session import DQChatSession

from src.async_llm_client import AsyncLLMClient
from src.async_reporter import AsyncDQReporter

async def main():
    """Run the report workflow and optional interactive chat session.

    Returns:
        None

    """
    db = Database()
    if not db.test_connection():
        sys.exit(1)

    inspector = DBInspector(db)
    reporter = DQReporter(inspector)

    profiles = reporter.run_full_report()
    reporter.print_report(profiles)
    summary = reporter.get_summary(profiles)
    reporter.print_summary(summary)

    llm = LLMClient()
    async_llm = AsyncLLMClient()
    async_reporter = AsyncDQReporter(inspector, async_llm, reporter)

    if await async_llm.is_available():
        print(f"Running concurrent AI analysis on {len(profiles)} tables...")
        start = time.time()
        await async_reporter.run_full_analysis(profiles)
        elapsed = round(time.time() - start, 2)
        print(f"\n Async analysis completed in {elapsed}s")

        start_chat = input("Start interactive chat session? (y/n):")
        if start_chat.lower() == "y":
            dq_chat = DQChatSession(llm, inspector, reporter)
            dq_chat.start(profiles)

        print("Goodbye!")
    else:
        print("AI is not available for a detailed analysis.")

asyncio.run(main())

