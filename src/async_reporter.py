import asyncio
from concurrent.futures import ThreadPoolExecutor

from src.async_llm_client import AsyncLLMClient
from src.models import TableProfile
from src.db_inspector import DBInspector
from src.reporter import DQReporter

class AsyncDQReporter:
    """Coordinate concurrent AI analysis across multiple table profiles.

    Attributes:
        inspector: Database inspector used to fetch null statistics.
        llm_client: Async LLM client used for table analysis.
        reporter: Reporter used to print completed analysis results.

    """
    def __init__(self, inspector: DBInspector, llm_client: AsyncLLMClient, reporter: DQReporter):
        """Store dependencies required for concurrent report enrichment.

        Args:
            inspector: Database inspector used for table profiling data.
            llm_client: Async LLM client used for table analysis.
            reporter: Reporter used to render completed analysis.

        """
        self.inspector = inspector
        self.llm_client = llm_client
        self.reporter = reporter

    async def analyse_all_tables(self, profiles: list[TableProfile]):
        """Analyze all supplied tables concurrently.

        Args:
            profiles: Table profiles to analyze.

        Returns:
            list: Analysis results or exceptions returned by the concurrent tasks.

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
        """Run concurrent analysis for all tables and print each result.

        Args:
            profiles: Table profiles to analyze.

        Returns:
            None

        """
        table_analysis = await self.analyse_all_tables(profiles)
        for ta in table_analysis:
            if isinstance(ta, Exception) or ta is None:
                continue
            self.reporter.print_ai_table_analysis(ta)


    async def run_sync_in_thread(self, sync_func, *args):
        """Run a synchronous function in a worker thread.

        Args:
            sync_func: Synchronous callable to execute.
            *args: Positional arguments forwarded to the callable.

        Returns:
            Any: Result returned by the synchronous callable.

        """
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, sync_func, *args)

