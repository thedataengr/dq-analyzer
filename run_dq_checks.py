from src.dq_checker import DQChecker
from src.database import Database
from src.db_inspector import DBInspector

def print_table_result(result: dict):
    """Print the validation summary for a single table.

    Args:
        result: Aggregated validation output for one table.

    Returns:
        None

    """
    total = result["total_checks"]
    passed = result["passed"]
    table = result["table"]

    print(f"\n{'=' * 60}")
    print(f"{table} — {passed}/{total} checks passed")
    print(f"{'=' * 60}")

    for check in result["checks"]:
        status = "✅" if check["passed"] else "❌"
        column_info = f" on {check['column']}" if check.get("column") else ""
        print(f"{status} {check['check']}{column_info}")

        if not check["passed"] and check.get('failed_rows'):
            print(f"   Failed rows: {check['failed_rows']} ({round(check['failed_pct'],2)}%)")


def main():
    """Run predefined data quality checks for every discovered table.

    Returns:
        None

    """
    db = Database()
    if not db.test_connection():
        return

    inspector = DBInspector(db)
    checker = DQChecker(db.database_url)

    print("Running DQ checks on all tables...")
    results = checker.run_all_checks(inspector.get_table_names())

    total_checks = sum(r["total_checks"] for r in results)
    total_passed = sum(r["passed"] for r in results)

    for result in results:
        print_table_result(result)

    print(f"\nOverall: {total_passed}/{total_checks} checks passed across {len(results)} tables")


if __name__ == "__main__":
    main()
