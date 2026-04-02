import great_expectations as gx
from great_expectations import ExpectationSuite
from great_expectations.expectations import (
    ExpectColumnValuesToNotBeNull,
    ExpectColumnValuesToBeBetween,
    ExpectColumnValuesToBeInSet,
    ExpectColumnValuesToBeUnique,
    ExpectTableRowCountToBeBetween
)

class DQChecker:
    """Run predefined Great Expectations suites against known tables.

    Attributes:
        context: Ephemeral Great Expectations context.
        datasource: Postgres datasource registered with the context.

    """
    def __init__(self, connection_string: str):
        """Create an ephemeral Great Expectations context for Postgres checks.

        Args:
            connection_string: Database connection string for the Postgres
                datasource.

        """
        self.context = gx.get_context(mode="ephemeral")

        self.datasource = self.context.data_sources.add_postgres(
            name="pg_datasource",
            connection_string=connection_string
        )

    def _get_suite_for_table(self, table_name: str) -> ExpectationSuite:
        """Create or retrieve the expectation suite for a supported table.

        Args:
            table_name: Name of the table whose suite should be loaded.

        Returns:
            ExpectationSuite: Great Expectations suite for the table.

        """
        suite_name = f"{table_name}_suite"
        try:
            suite = self.context.suites.add(ExpectationSuite(name=suite_name))
        except Exception:
            suite = self.context.suites.get(suite_name)
            return suite

        match table_name:
            case "orders":
                suite.add_expectation(
                    ExpectColumnValuesToBeUnique(column="id")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="customer_id")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="amount")
                )
                suite.add_expectation(
                    ExpectColumnValuesToBeBetween(column="amount", min_value=0, max_value=1_000_000)
                )
                suite.add_expectation(
                    ExpectColumnValuesToBeInSet(column="status", value_set=["pending", "completed", "cancelled"])
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="created_at")
                )
                suite.add_expectation(
                    ExpectTableRowCountToBeBetween(min_value=1)
                )
            case "customers":
                suite.add_expectation(
                    ExpectColumnValuesToBeUnique(column="id")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="name")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="email")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="created_at")
                )
            case "products":
                suite.add_expectation(
                    ExpectColumnValuesToBeUnique(column="id")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="name")
                )
                suite.add_expectation(
                    ExpectColumnValuesToNotBeNull(column="price")
                )
                suite.add_expectation(
                    ExpectColumnValuesToBeBetween(column="price", min_value=0, max_value=100_000)
                )
                suite.add_expectation(
                    ExpectColumnValuesToBeBetween(column="stock_count", min_value=0, max_value=1_000_000)
                )
            case _:
                raise ValueError(f"Invalid table name provided: '{table_name}'")
        return suite

    def run_checks(self, table_name: str) -> dict:
        """Execute the configured expectation suite for a single table.

        Args:
            table_name: Name of the table to validate.

        Returns:
            dict: Structured validation summary for the table.

        """
        try:
            asset = self.datasource.add_table_asset(name=table_name, table_name=table_name)
        except Exception:
            asset = self.datasource.get_asset(name=table_name)
        batch_definition = asset.add_batch_definition_whole_table("full_table")

        suite = self._get_suite_for_table(table_name)
        batch = batch_definition.get_batch()
        validation_result = batch.validate(suite)

        result_summary = {
            "table": table_name,
            "total_checks": validation_result["statistics"]["evaluated_expectations"],
            "passed": validation_result["statistics"]["successful_expectations"],
            "failed": validation_result["statistics"]["unsuccessful_expectations"],
            "checks": [
                {
                    "passed": result["success"],
                    "check": result["expectation_config"]["type"],
                    "column": result["expectation_config"]["kwargs"].get("column", ""),
                    "failed_rows": result["result"].get("unexpected_count", 0),
                    "failed_pct": result["result"].get("unexpected_percent", 0.0)
                }
                for result in validation_result["results"] if
                          result["expectation_config"]["type"].startswith("expect_column_")
            ] + [
                {
                    "passed": result["success"],
                    "check": result["expectation_config"]["type"],
                }
                for result in validation_result["results"] if
                        result["expectation_config"]["type"].startswith("expect_table_")
            ]
        }
        return dict(result_summary)

    def run_all_checks(self, tables: list) -> list[dict]:
        """Run data quality checks for each table in the provided list.

        Args:
            tables: Table names to validate.

        Returns:
            list[dict]: Validation summaries for each table.

        """
        return [self.run_checks(table) for table in tables]




