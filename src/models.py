
class TableProfile:
    """Store basic profiling metrics and severity for a database table.

    Attributes:
        name: Table name.
        row_count: Number of rows in the table.
        null_count: Total number of null values across the table.
        column_count: Number of columns in the table.
        null_pct: Computed percentage of null values across all fields.

    """
    def __init__(self, name: str, row_count: int, null_count: int, column_count: int):
        """Initialize a table profile and precompute its null percentage.

        Args:
            name: Table name.
            row_count: Number of rows in the table.
            null_count: Total number of null values across the table.
            column_count: Number of columns in the table.

        """
        self.name = name
        self.row_count = row_count
        self.null_count = null_count
        self.column_count = column_count
        self.null_pct = self._calculate_null_pct()

    def _calculate_null_pct(self) -> float:
        """Calculate the percentage of null fields in the table.

        Returns:
            float: Percentage of null fields across the table.

        """
        try:
            return round((self.null_count / (self.row_count*self.column_count)) * 100,2)
        except ZeroDivisionError:
            return 0.0
        except TypeError as e:
            print(f"Invalid input type: {e}")
            return 0.0

    def get_status(self) -> str:
        """Return the severity status derived from the null percentage.

        Returns:
            str: `"critical"` if null percentage exceeds 10, `"warning"` if it
            exceeds 5, or `"ok"` otherwise.

        """
        if self.null_pct > 10:
            status = "critical"
        elif self.null_pct > 5:
            status = "warning"
        else:
            status = "ok"

        return status

    def __str__(self):
        """Return a readable one-line summary of the table profile.

        Returns:
            str: Human-readable representation of the table profile.

        """
        status = self.get_status()
        return(f'Table "{self.name}" | Rows: {self.row_count} | Columns: {self.column_count} | Null %: {self.null_pct} | Status: {status}')
