from src.db_inspector import DBInspector
from src.models import TableProfile
import csv

class DQReporter:
    def __init__(self, inspector: DBInspector):
        self.inspector = inspector

    def run_full_report(self) -> list[TableProfile]:
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
        print("=============================================================================")
        print("DATA QUALITY REPORT")
        print("=============================================================================")

        for profile in profiles:
            print(profile)

        print("=============================================================================\n")

    def get_summary(self,profiles: list[TableProfile]) -> dict:
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
        print("\n============================================================")
        print("AI INTERPRETATION")
        print("============================================================")
        print(ai_response)
        print("============================================================")

    def print_ai_table_analysis(self, table_analysis: dict):
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


