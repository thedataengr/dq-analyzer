import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.async_llm_client import AsyncLLMClient
from src.models import TableProfile
from src.db_inspector import DBInspector
from src.reporter import DQReporter

class AsyncDQReporter:
    def __init__(self, inspector: DBInspector, llm_client: AsyncLLMClient, reporter: DQReporter):
        self.inspector = inspector
        self.llm_client = llm_client
        self.reporter = reporter

    async def analyse_all_tables(self, profiles: list[TableProfile]):
        """
        uses asyncio.gather to analyse ALL tables concurrently, returns list of analysis dicts
        :param profiles:
        :return:
        """
        # Fetch all null stats concurrently
        null_stats_list = await asyncio.gather(*[
            self.run_sync_in_thread(self.inspector.get_null_counts, p.name)
            for p in profiles
        ], return_exceptions=True)

        llm_tasks = []
        for profile, null_stats in zip(profiles, null_stats_list):
            if isinstance(null_stats, Exception):
                print(f"Failed to fetch null stats for {profile.name}: {null_stats}")
                llm_tasks.append(asyncio.sleep(0))  # placeholder
            else:
                llm_tasks.append(self.llm_client.analyse_table(profile.name, null_stats, profile.row_count))

        return await asyncio.gather(*llm_tasks, return_exceptions=True)

    async def run_full_analysis(self, profiles: list[TableProfile]):
        """
        calls analyse_all_tables and prints each result
        :param profiles: list[TableProfile]
        :return: None
        """
        table_analysis = await self.analyse_all_tables(profiles)
        for ta in table_analysis:
            if isinstance(ta, Exception) or ta is None:
                continue
            self.reporter.print_ai_table_analysis(ta)


    async def run_sync_in_thread(self, sync_func, *args):
        """
        Run a synchronous function in a thread pool without blocking the event loop
        :param sync_func: name of synchronous function
        :param args: arguments of synchronous function
        :return: result of synchronous function
        """
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, sync_func, *args)

