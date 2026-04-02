from src.db_inspector import DBInspector
from src.models import TableProfile
import csv

class DQReporter:
    """Generate, print, and export data quality profiling reports.

    Attributes:
        inspector: Database inspector used to gather profiling metrics.

    """
    def __init__(self, inspector: DBInspector):
        """Store the inspector used to gather table profiling metrics.

        Args:
            inspector: Database inspector used for table profiling.

        """
        self.inspector = inspector

    def run_full_report(self) -> list[TableProfile]:
        """Profile every table and return the resulting table summaries.

        Returns:
            list[TableProfile]: Profiles for all discovered tables.

        """
        table_names = self.inspector.get_table_names()

        tables = []
        for table in table_names:
            row_count = self.inspector.get_row_count(table)
            column_count = self.inspector.get_column_count(table)
            null_counts = self.inspector.get_null_counts(table)
            total_null_count = sum(null_counts.values())
            tables.append(TableProfile(table, row_count, total_null_count, column_count))

        return tables

    def print_report(self, profiles: list[TableProfile]) :
        """Print the full per-table data quality report to stdout.

        Args:
            profiles: Table profiles to print.

        Returns:
            None

        """
        print("=============================================================================")
        print("DATA QUALITY REPORT")
        print("=============================================================================")

        for profile in profiles:
            print(profile)

        print("=============================================================================\n")

    def get_summary(self,profiles: list[TableProfile]) -> dict:
        """Aggregate a collection of table profiles into summary counts.

        Args:
            profiles: Table profiles to summarize.

        Returns:
            dict: Summary counts and the most problematic table name.

        """
        total_tables_cnt = len(profiles)
        critical_tables_cnt = len([t for t in profiles if t.get_status() == "critical"])
        warning_tables_cnt = len([t for t in profiles if t.get_status() == "warning"])
        ok_tables_cnt = len([t for t in profiles if t.get_status() == "ok"])
        most_problematic_table = max(profiles, key=lambda x: x.null_pct).name

        return {
            "total_tables": total_tables_cnt,
            "critical_tables": critical_tables_cnt,
            "warning_tables": warning_tables_cnt,
            "ok_tables": ok_tables_cnt,
            "most_problematic_table": most_problematic_table,
        }

    def print_summary(self, summary: dict):
        """Print the aggregated report summary to stdout.

        Args:
            summary: Report summary values to print.

        Returns:
            None

        """
        print("===============================================")
        print("SUMMARY")
        print("===============================================")

        print(f"Total tables     : {summary['total_tables']}")
        print(f"Critical tables  : {summary['critical_tables']}")
        print(f"Warning tables   : {summary['warning_tables']}")
        print(f"OK tables        : {summary['ok_tables']}")
        print(f"Most problematic : {summary['most_problematic_table']}")
        print("================================================")


    def export_report_csv(self, profiles: list[TableProfile], filepath: str):
        """Write the table profiles to a CSV report file.

        Args:
            profiles: Table profiles to export.
            filepath: Destination path for the CSV file.

        Returns:
            None

        """
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["table_name","row_count","column_count","null_pct","status"])
            writer.writeheader()
            for p in profiles:
                writer.writerow({
                    "table_name": p.name,
                    "row_count": p.row_count,
                    "column_count": p.column_count,
                    "null_pct": p.null_pct,
                    "status": p.get_status()
                })

    def print_ai_interpretation(self, ai_response: str):
        """Print a high-level AI interpretation of the report.

        Args:
            ai_response: AI-generated summary text.

        Returns:
            None

        """
        print("\n============================================================")
        print("AI INTERPRETATION")
        print("============================================================")
        print(ai_response)
        print("============================================================")

    def print_ai_table_analysis(self, table_analysis: dict):
        """Print AI-generated analysis details for a single table.

        Args:
            table_analysis: Structured AI analysis for one table.

        Returns:
            None

        """
        print("================================================================================")
        print(f"AI ANALYSIS: {table_analysis['table']}")
        print("================================================================================")
        print(f"Overall Severity : {table_analysis['overall_severity']}")
        print(f"Summary          : {table_analysis['summary']}\n")

        print("Column Issues:")
        for issue in table_analysis['issues']:
            print(f"\t{issue['column']}\t| {issue['null_pct']}\t| {issue['severity']}")
            print(f"\t→ {issue['impact']}")
            print(f"\t→ Recommendation: {issue['recommendation']}\n")


